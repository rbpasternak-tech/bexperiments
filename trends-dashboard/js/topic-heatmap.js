/**
 * topic-heatmap.js
 * Renders an HTML heatmap table: rows = topics, columns = digest dates.
 * Cell intensity reflects mention count. Collapsible rows and sparkline trends.
 */

import { heatmapColor, esc, formatShortDate, emptyState } from './chart-utils.js';

const DEFAULT_ROWS = 10;

/**
 * @param {HTMLElement} container
 * @param {Object}      data
 */
export function renderTopicHeatmap(container, data) {
  const timeSeries = data.topicTimeSeries || [];
  if (timeSeries.length === 0) {
    container.innerHTML = emptyState('Topic Heatmap');
    return;
  }

  const dateSet = new Set();
  for (const ts of timeSeries) {
    for (const pt of ts.series) dateSet.add(pt.date);
  }
  const dates = [...dateSet].sort();

  const rows = timeSeries.map((ts) => {
    const countByDate = new Map(ts.series.map((p) => [p.date, p.count]));
    const total = ts.series.reduce((s, p) => s + p.count, 0);
    const counts = dates.map((d) => countByDate.get(d) || 0);
    return { topic: ts.topic, countByDate, total, counts };
  });

  rows.sort((a, b) => b.total - a.total);

  let globalMax = 0;
  for (const r of rows) {
    for (const [, c] of r.countByDate) {
      if (c > globalMax) globalMax = c;
    }
  }

  let expanded = false;

  function render() {
    const visible = expanded ? rows : rows.slice(0, DEFAULT_ROWS);
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const lightText = isDark ? '#e0e7ff' : '#1E1B4B';

    let html = '<h2 class="section-title">Topic Heatmap</h2>';
    html += '<div class="heatmap-wrapper">';
    html += '<table class="heatmap-table">';

    html += '<thead><tr><th class="heatmap-topic-header">Topic</th>';
    for (const d of dates) {
      html += `<th class="heatmap-date-header">${formatShortDate(d)}</th>`;
    }
    html += '<th class="heatmap-trend-header">Trend</th>';
    html += '</tr></thead>';

    html += '<tbody>';
    for (const row of visible) {
      html += '<tr>';
      html += `<td class="heatmap-topic-name" data-topic="${esc(row.topic)}">${esc(row.topic)}</td>`;

      for (const d of dates) {
        const count = row.countByDate.get(d) || 0;
        const bg = heatmapColor(count, globalMax);
        const textColor = count / globalMax > 0.5 ? '#fff' : lightText;
        html += `<td class="heatmap-cell" style="background:${bg};color:${textColor}" title="${esc(row.topic)} \u2014 ${d}: ${count}">${count || ''}</td>`;
      }

      html += `<td class="heatmap-trend">${sparkline(row.counts)}</td>`;
      html += '</tr>';
    }
    html += '</tbody></table></div>';

    if (rows.length > DEFAULT_ROWS) {
      html += `<button class="heatmap-expand-btn" id="heatmap-expand">
        ${expanded ? `Show Top ${DEFAULT_ROWS}` : `Show All ${rows.length} Topics`}
      </button>`;
    }

    container.innerHTML = html;

    // Wire expand button
    const expandBtn = document.getElementById('heatmap-expand');
    if (expandBtn) {
      expandBtn.addEventListener('click', () => {
        expanded = !expanded;
        render();
      });
    }

    // Wire topic click filter
    container.querySelectorAll('.heatmap-topic-name').forEach((el) => {
      el.style.cursor = 'pointer';
      el.addEventListener('click', () => {
        if (typeof window.filterByTopic === 'function') {
          window.filterByTopic(el.dataset.topic);
        }
      });
    });
  }

  render();
}

function sparkline(counts) {
  if (counts.length < 2) return '<span class="trend-dash">&mdash;</span>';

  const max = Math.max(...counts, 1);
  const w = 60;
  const h = 20;
  const step = w / (counts.length - 1);

  const points = counts.map((c, i) => {
    const x = i * step;
    const y = h - (c / max) * (h - 2) - 1;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const last = counts[counts.length - 1];
  const prev = counts[counts.length - 2];
  const color = last > prev ? '#22c55e' : last < prev ? '#ef4444' : '#94a3b8';

  return `<svg class="sparkline" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    <polyline points="${points.join(' ')}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;
}
