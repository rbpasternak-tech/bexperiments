/**
 * ai-economy.js
 * Renders AI Economy section: summary stat cards, funding bar chart,
 * and scrollable event list.
 */

import { EVENT_COLORS, formatCurrency, formatNumber } from './chart-utils.js';

/* ---- Module-level chart reference ---- */
let fundingChartInstance = null;

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

/**
 * @param {HTMLElement} container
 * @param {Object}      data — full dashboard data (uses data.aggregatedEconomy)
 */
export function renderAIEconomy(container, data) {
  const events = data.aggregatedEconomy || [];

  if (events.length === 0) {
    container.innerHTML = emptyState('AI Economy Tracker');
    return;
  }

  /* ---- Compute stats ---- */
  const stats = computeStats(events);

  /* ---- Build HTML ---- */
  let html = '<h2 class="section-title">AI Economy Tracker</h2>';

  // Summary cards
  html += '<div class="quick-stats">';
  html += statCard('Total Funding', formatCurrency(stats.totalFunding));
  html += statCard('Acquisitions', formatNumber(stats.acquisitions));
  html += statCard('Partnerships', formatNumber(stats.partnerships));
  html += statCard('Layoffs', formatNumber(stats.layoffs));
  html += '</div>';

  // Funding chart
  if (stats.fundingByDate.length > 0) {
    html += `<div class="chart-container" style="position:relative;height:300px;">
      <canvas id="ai-economy-funding-chart"></canvas>
    </div>`;
  }

  // Event list
  html += '<div class="event-list-wrapper">';
  html += '<h3 class="subsection-title">Recent Events</h3>';
  html += '<div class="event-list">';
  for (const ev of events.slice(0, 50)) {
    html += eventItem(ev);
  }
  html += '</div></div>';

  container.innerHTML = html;

  /* ---- Render funding chart ---- */
  if (stats.fundingByDate.length > 0) {
    renderFundingChart(stats.fundingByDate);
  }
}

/* ------------------------------------------------------------------ */
/*  Stats Computation                                                  */
/* ------------------------------------------------------------------ */

function computeStats(events) {
  let totalFunding = 0;
  let acquisitions = 0;
  let partnerships = 0;
  let layoffs = 0;

  // Aggregate funding by digest date
  const fundingMap = new Map();

  for (const ev of events) {
    const type = (ev.type || ev.event_type || '').toLowerCase();

    if (type === 'funding') {
      const amount = ev.amount_usd || ev.amount || ev.funding_amount || 0;
      totalFunding += amount;
      const date = ev._digestDate || 'unknown';
      fundingMap.set(date, (fundingMap.get(date) || 0) + amount);
    }
    if (type === 'acquisition') acquisitions++;
    if (type === 'partnership') partnerships++;
    if (type === 'layoff')      layoffs++;
  }

  const fundingByDate = [...fundingMap.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, amount]) => ({ date, amount }));

  return { totalFunding, acquisitions, partnerships, layoffs, fundingByDate };
}

/* ------------------------------------------------------------------ */
/*  Funding Bar Chart                                                  */
/* ------------------------------------------------------------------ */

function renderFundingChart(fundingByDate) {
  const ctx = document.getElementById('ai-economy-funding-chart');
  if (!ctx) return;

  if (fundingChartInstance) fundingChartInstance.destroy();

  fundingChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: fundingByDate.map((d) => formatShortDate(d.date)),
      datasets: [
        {
          label: 'Funding',
          data: fundingByDate.map((d) => d.amount),
          backgroundColor: EVENT_COLORS.funding + 'CC', // slight transparency
          borderColor: EVENT_COLORS.funding,
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => formatCurrency(ctx.raw),
          },
        },
      },
      scales: {
        x: { title: { display: true, text: 'Week' } },
        y: {
          title: { display: true, text: 'Funding Amount' },
          beginAtZero: true,
          ticks: {
            callback: (v) => formatCurrency(v),
          },
        },
      },
    },
  });
}

/* ------------------------------------------------------------------ */
/*  Event List Item                                                    */
/* ------------------------------------------------------------------ */

function eventItem(ev) {
  const type     = ev.type || ev.event_type || 'event';
  const entity   = esc(ev.entity || ev.company || ev.organization || '');
  const headline = esc(ev.headline || ev.title || ev.description || '');
  const color    = EVENT_COLORS[type.toLowerCase()] || '#6366F1';
  const source   = renderSourceLink(ev);

  return `
    <div class="event-item">
      <span class="event-type-badge" style="background:${color}">${esc(type)}</span>
      ${entity ? `<strong class="event-entity">${entity}</strong>` : ''}
      <span class="event-headline">${headline}</span>
      ${source}
    </div>`;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function renderSourceLink(ev) {
  const url = ev.source_url || ev.url || ev.link || '';
  const name = ev.source || ev.source_name || '';
  if (url) {
    const label = name || domainFromUrl(url);
    return `<a href="${esc(url)}" target="_blank" rel="noopener" class="source-link">${esc(label)}</a>`;
  }
  if (name) return `<span class="source-name">${esc(name)}</span>`;
  return '';
}

function domainFromUrl(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); }
  catch { return url; }
}

function statCard(label, value) {
  return `
    <div class="stat-card">
      <span class="stat-label">${label}</span>
      <span class="stat-value">${value}</span>
    </div>`;
}

function formatShortDate(dateStr) {
  try {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch { return dateStr; }
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
