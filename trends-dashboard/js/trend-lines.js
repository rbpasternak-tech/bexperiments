/**
 * trend-lines.js
 * Renders a Chart.js line chart of the top 10 topics over time,
 * plus emerging / fading topic badges below.
 */

import { colorForCategory } from './chart-utils.js';

/* ---- Module-level chart reference for cleanup ---- */
let lineChartInstance = null;

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

/**
 * @param {HTMLElement} container
 * @param {string}      canvasId — id for the <canvas> element
 * @param {Object}      data     — full dashboard data
 */
export function renderTrendLines(container, canvasId, data) {
  const timeSeries = data.topicTimeSeries || [];
  const trends     = data.trendAnalysis || { emerging: [], fading: [] };

  if (timeSeries.length === 0) {
    container.innerHTML = emptyState('Trend Lines');
    return;
  }

  /* ---- Pick top 10 topics by total mentions ---- */
  const ranked = timeSeries
    .map((ts) => ({
      ...ts,
      total: ts.series.reduce((s, p) => s + p.count, 0),
    }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 10);

  /* ---- Collect all dates (chronological) ---- */
  const dateSet = new Set();
  for (const ts of ranked) {
    for (const pt of ts.series) dateSet.add(pt.date);
  }
  const labels = [...dateSet].sort();

  /* ---- Build Chart.js datasets ---- */
  const datasets = ranked.map((ts) => {
    const countByDate = new Map(ts.series.map((p) => [p.date, p.count]));
    return {
      label: ts.topic,
      data: labels.map((d) => countByDate.get(d) || 0),
      borderColor: colorForCategory(ts.topic.toLowerCase().replace(/\s+/g, '_')),
      backgroundColor: colorForCategory(ts.topic.toLowerCase().replace(/\s+/g, '_')),
      fill: false,
    };
  });

  /* ---- Render ---- */
  let html = '<h2 class="section-title">Trend Lines</h2>';
  html += `<div class="chart-container" style="position:relative;height:380px;">
    <canvas id="${canvasId}"></canvas>
  </div>`;
  html += trendBadges(trends);
  container.innerHTML = html;

  /* ---- Create chart ---- */
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  if (lineChartInstance) lineChartInstance.destroy();

  lineChartInstance = new Chart(ctx, {
    type: 'line',
    data: { labels: labels.map(formatShortDate), datasets },
    options: {
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'bottom' },
        tooltip: { mode: 'index', intersect: false },
      },
      scales: {
        x: { title: { display: true, text: 'Week' } },
        y: { title: { display: true, text: 'Mentions' }, beginAtZero: true },
      },
    },
  });
}

/* ------------------------------------------------------------------ */
/*  Emerging / Fading Badges                                           */
/* ------------------------------------------------------------------ */

function trendBadges(trends) {
  const { emerging = [], fading = [] } = trends;
  if (emerging.length === 0 && fading.length === 0) return '';

  let html = '<div class="trend-badges">';

  if (emerging.length) {
    html += '<div class="badge-group">';
    html += '<span class="badge-group-label">Emerging</span>';
    for (const t of emerging) {
      html += `<span class="badge badge-emerging">${esc(t)}</span>`;
    }
    html += '</div>';
  }

  if (fading.length) {
    html += '<div class="badge-group">';
    html += '<span class="badge-group-label">Fading</span>';
    for (const t of fading) {
      html += `<span class="badge badge-fading">${esc(t)}</span>`;
    }
    html += '</div>';
  }

  html += '</div>';
  return html;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatShortDate(dateStr) {
  try {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

function esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

function emptyState(title) {
  return `
    <h2 class="section-title">${title}</h2>
    <div class="empty-state">
      <p>No data yet</p>
    </div>`;
}
