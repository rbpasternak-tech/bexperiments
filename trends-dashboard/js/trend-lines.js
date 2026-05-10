/**
 * trend-lines.js
 * Renders a Chart.js line chart of the top topics over time,
 * with gradient fills, hover highlighting, and a show-more toggle.
 */

import { colorForCategory, esc, formatShortDate, emptyState } from './chart-utils.js';

let lineChartInstance = null;
const DEFAULT_SHOW = 5;

/**
 * @param {HTMLElement} container
 * @param {string}      canvasId
 * @param {Object}      data
 */
export function renderTrendLines(container, canvasId, data) {
  const timeSeries = data.topicTimeSeries || [];
  const trends     = data.trendAnalysis || { emerging: [], fading: [] };

  if (timeSeries.length === 0) {
    container.innerHTML = emptyState('Trend Lines');
    return;
  }

  const ranked = timeSeries
    .map((ts) => ({
      ...ts,
      total: ts.series.reduce((s, p) => s + p.count, 0),
    }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 10);

  const dateSet = new Set();
  for (const ts of ranked) {
    for (const pt of ts.series) dateSet.add(pt.date);
  }
  const labels = [...dateSet].sort();

  let showAll = false;

  function buildAndRender() {
    const visible = showAll ? ranked : ranked.slice(0, DEFAULT_SHOW);

    let html = '<h2 class="section-title">Trend Lines</h2>';
    if (ranked.length > DEFAULT_SHOW) {
      html += `<div class="trend-toggle-row">
        <button class="trend-toggle-btn" id="trend-toggle-btn">
          ${showAll ? `Show Top ${DEFAULT_SHOW}` : `Show All ${ranked.length}`}
        </button>
      </div>`;
    }
    html += `<div class="chart-container" style="position:relative;height:380px;">
      <canvas id="${canvasId}"></canvas>
    </div>`;
    html += trendBadges(trends);
    container.innerHTML = html;

    // Wire toggle
    const toggleBtn = document.getElementById('trend-toggle-btn');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        showAll = !showAll;
        buildAndRender();
      });
    }

    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const datasets = visible.map((ts) => {
      const countByDate = new Map(ts.series.map((p) => [p.date, p.count]));
      const color = colorForCategory(ts.topic.toLowerCase().replace(/\s+/g, '_'));
      return {
        label: ts.topic,
        data: labels.map((d) => countByDate.get(d) || 0),
        borderColor: color,
        backgroundColor: color + '18',
        fill: 'origin',
        pointBackgroundColor: color,
        pointBorderColor: '#fff',
        pointBorderWidth: 1,
      };
    });

    if (lineChartInstance) lineChartInstance.destroy();

    lineChartInstance = new Chart(ctx, {
      type: 'line',
      data: { labels: labels.map(formatShortDate), datasets },
      options: {
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            position: 'bottom',
            onHover: (e, item) => highlightDataset(item.datasetIndex, true),
            onLeave: () => highlightDataset(-1, false),
          },
          tooltip: { mode: 'index', intersect: false },
        },
        scales: {
          x: { title: { display: true, text: 'Week' } },
          y: { title: { display: true, text: 'Mentions' }, beginAtZero: true },
        },
        onHover: (e, elements) => {
          if (elements.length > 0) {
            highlightDataset(elements[0].datasetIndex, true);
          } else {
            highlightDataset(-1, false);
          }
        },
      },
    });
  }

  function highlightDataset(activeIdx, hovering) {
    if (!lineChartInstance) return;
    const datasets = lineChartInstance.data.datasets;
    for (let i = 0; i < datasets.length; i++) {
      const ds = datasets[i];
      if (hovering && activeIdx >= 0) {
        ds.borderWidth = i === activeIdx ? 3.5 : 1;
        ds.borderColor = i === activeIdx
          ? ds._originalColor || ds.borderColor
          : (ds._originalColor || ds.borderColor) + '40';
      } else {
        ds.borderWidth = 2;
        ds.borderColor = ds._originalColor || ds.borderColor;
      }
      if (!ds._originalColor) ds._originalColor = ds.borderColor;
    }
    lineChartInstance.update('none');
  }

  buildAndRender();
}

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
