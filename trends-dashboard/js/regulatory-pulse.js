/**
 * regulatory-pulse.js
 * Renders the Regulatory Pulse section:
 *   - Horizontal stacked bar chart: jurisdictions x sentiment
 *   - Doughnut chart: event type distribution
 *   - Timeline list of regulatory events
 */

import { SENTIMENT_COLORS, formatNumber, esc, capitalize, formatShortDate, emptyState } from './chart-utils.js';

/* ---- Module-level chart references ---- */
let barChartInstance = null;
let doughnutChartInstance = null;

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

/**
 * @param {HTMLElement} container
 * @param {Object}      data — full dashboard data (uses data.aggregatedRegulatory)
 */
export function renderRegulatoryPulse(container, data) {
  const events = data.aggregatedRegulatory || [];

  if (events.length === 0) {
    container.innerHTML = emptyState('Regulatory Pulse');
    return;
  }

  /* ---- Aggregate data ---- */
  const { jurisdictionSentiment, typeCounts } = aggregate(events);

  /* ---- Build HTML ---- */
  let html = '<h2 class="section-title">Regulatory Pulse</h2>';

  // Charts row
  html += '<div class="reg-charts-row">';

  // Jurisdiction bar chart
  html += `<div class="reg-chart-col">
    <h3 class="subsection-title">By Jurisdiction &amp; Sentiment</h3>
    <div class="chart-container" style="position:relative;height:320px;">
      <canvas id="reg-jurisdiction-chart"></canvas>
    </div>
  </div>`;

  // Event type doughnut
  html += `<div class="reg-chart-col reg-chart-col-small">
    <h3 class="subsection-title">Event Types</h3>
    <div class="chart-container" style="position:relative;height:320px;">
      <canvas id="reg-type-chart"></canvas>
    </div>
  </div>`;

  html += '</div>'; // .reg-charts-row

  // Timeline
  html += '<div class="event-list-wrapper">';
  html += '<h3 class="subsection-title">Regulatory Timeline</h3>';
  html += '<div class="event-list">';
  for (const ev of events.slice(0, 40)) {
    html += timelineItem(ev);
  }
  html += '</div></div>';

  container.innerHTML = html;

  /* ---- Render charts ---- */
  renderJurisdictionChart(jurisdictionSentiment);
  renderTypeChart(typeCounts);
}

/* ------------------------------------------------------------------ */
/*  Data Aggregation                                                   */
/* ------------------------------------------------------------------ */

function aggregate(events) {
  // jurisdictionSentiment: { jurisdiction: { positive: N, neutral: N, ... } }
  const js = {};
  // typeCounts: { type: N }
  const tc = {};

  for (const ev of events) {
    const jur = ev.jurisdiction || ev.region || 'Unknown';
    const sentiment = (ev.sentiment || 'neutral').toLowerCase();
    const type = ev.type || ev.event_type || 'other';

    if (!js[jur]) js[jur] = {};
    js[jur][sentiment] = (js[jur][sentiment] || 0) + 1;

    tc[type] = (tc[type] || 0) + 1;
  }

  return { jurisdictionSentiment: js, typeCounts: tc };
}

/* ------------------------------------------------------------------ */
/*  Jurisdiction Horizontal Bar Chart                                  */
/* ------------------------------------------------------------------ */

function renderJurisdictionChart(jsBySentiment) {
  const ctx = document.getElementById('reg-jurisdiction-chart');
  if (!ctx) return;

  const jurisdictions = Object.keys(jsBySentiment).sort();
  const sentimentKeys = [
    ...new Set(
      jurisdictions.flatMap((j) => Object.keys(jsBySentiment[j]))
    ),
  ].sort();

  const datasets = sentimentKeys.map((s) => ({
    label: capitalize(s),
    data: jurisdictions.map((j) => jsBySentiment[j][s] || 0),
    backgroundColor: SENTIMENT_COLORS[s] || '#94A3B8',
    borderRadius: 3,
  }));

  if (barChartInstance) barChartInstance.destroy();

  barChartInstance = new Chart(ctx, {
    type: 'bar',
    data: { labels: jurisdictions, datasets },
    options: {
      indexAxis: 'y',
      plugins: {
        legend: { position: 'bottom' },
        tooltip: { mode: 'index', intersect: false },
      },
      scales: {
        x: {
          stacked: true,
          title: { display: true, text: 'Events' },
          beginAtZero: true,
          ticks: { stepSize: 1 },
        },
        y: { stacked: true },
      },
    },
  });
}

/* ------------------------------------------------------------------ */
/*  Event Type Doughnut Chart                                          */
/* ------------------------------------------------------------------ */

function renderTypeChart(typeCounts) {
  const ctx = document.getElementById('reg-type-chart');
  if (!ctx) return;

  const labels = Object.keys(typeCounts);
  const values = labels.map((l) => typeCounts[l]);

  // Generate colors from a pleasing indigo/blue set
  const palette = [
    '#4F46E5', '#6366F1', '#818CF8', '#A5B4FC',
    '#3B82F6', '#60A5FA', '#93C5FD', '#7C3AED',
    '#8B5CF6', '#C4B5FD',
  ];
  const colors = labels.map((_, i) => palette[i % palette.length]);

  if (doughnutChartInstance) doughnutChartInstance.destroy();

  doughnutChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels.map(capitalize),
      datasets: [
        {
          data: values,
          backgroundColor: colors,
          borderWidth: 2,
          borderColor: '#fff',
        },
      ],
    },
    options: {
      cutout: '55%',
      plugins: {
        legend: { position: 'bottom' },
      },
    },
  });
}

/* ------------------------------------------------------------------ */
/*  Timeline List Item                                                 */
/* ------------------------------------------------------------------ */

function timelineItem(ev) {
  const jur     = esc(ev.jurisdiction || ev.region || '');
  const title   = esc(ev.title || ev.headline || ev.name || '');
  const summary = esc(ev.summary || ev.description || '');
  const date    = ev._digestDate || '';

  return `
    <div class="event-item reg-event">
      ${jur ? `<span class="jurisdiction-badge">${jur}</span>` : ''}
      ${date ? `<span class="event-date">${formatShortDate(date)}</span>` : ''}
      <strong class="event-title">${title}</strong>
      ${summary ? `<p class="event-summary">${summary}</p>` : ''}
    </div>`;
}

