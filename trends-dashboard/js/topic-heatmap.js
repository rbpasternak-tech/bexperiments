/**
 * topic-heatmap.js
 * Renders an HTML heatmap table: rows = topics, columns = digest dates.
 * Cell intensity reflects mention count. Includes trend arrows and click filtering.
 */

import { heatmapColor } from './chart-utils.js';

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

/**
 * @param {HTMLElement} container
 * @param {Object}      data — full dashboard data (uses data.digests, data.topicTimeSeries)
 */
export function renderTopicHeatmap(container, data) {
  const timeSeries = data.topicTimeSeries || [];
  if (timeSeries.length === 0) {
    container.innerHTML = emptyState('Topic Heatmap');
    return;
  }

  /* ---- Collect all dates (chronological) ---- */
  const dateSet = new Set();
  for (const ts of timeSeries) {
    for (const pt of ts.series) dateSet.add(pt.date);
  }
  const dates = [...dateSet].sort();

  /* ---- Build per-topic row data ---- */
  const rows = timeSeries.map((ts) => {
    const countByDate = new Map(ts.series.map((p) => [p.date, p.count]));
    const total = ts.series.reduce((s, p) => s + p.count, 0);
    return { topic: ts.topic, countByDate, total };
  });

  // Sort by total mentions descending
  rows.sort((a, b) => b.total - a.total);

  /* ---- Global max for color scaling ---- */
  let globalMax = 0;
  for (const r of rows) {
    for (const [, c] of r.countByDate) {
      if (c > globalMax) globalMax = c;
    }
  }

  /* ---- Render ---- */
  let html = '<h2 class="section-title">Topic Heatmap</h2>';
  html += '<div class="heatmap-wrapper">';
  html += '<table class="heatmap-table">';

  // Header
  html += '<thead><tr><th class="heatmap-topic-header">Topic</th>';
  for (const d of dates) {
    html += `<th class="heatmap-date-header">${formatShortDate(d)}</th>`;
  }
  html += '<th class="heatmap-trend-header">Trend</th>';
  html += '</tr></thead>';

  // Body
  html += '<tbody>';
  for (const row of rows) {
    html += '<tr>';
    html += `<td class="heatmap-topic-name" data-topic="${esc(row.topic)}">${esc(row.topic)}</td>`;

    for (const d of dates) {
      const count = row.countByDate.get(d) || 0;
      const bg = heatmapColor(count, globalMax);
      const textColor = count / globalMax > 0.5 ? '#fff' : '#1E1B4B';
      html += `<td class="heatmap-cell" style="background:${bg};color:${textColor}" title="${esc(row.topic)} &mdash; ${d}: ${count}">${count || ''}</td>`;
    }

    // Trend arrow: compare last two dates
    html += `<td class="heatmap-trend">${trendArrow(row.countByDate, dates)}</td>`;
    html += '</tr>';
  }
  html += '</tbody></table></div>';

  container.innerHTML = html;

  /* ---- Click handler: topic names trigger filter ---- */
  container.querySelectorAll('.heatmap-topic-name').forEach((el) => {
    el.style.cursor = 'pointer';
    el.addEventListener('click', () => {
      const topicName = el.dataset.topic;
      // filterByTopic is exposed globally by app.js
      if (typeof window.filterByTopic === 'function') {
        window.filterByTopic(topicName);
      }
    });
  });
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function trendArrow(countByDate, dates) {
  if (dates.length < 2) return '<span class="trend-dash">&mdash;</span>';
  const last = countByDate.get(dates[dates.length - 1]) || 0;
  const prev = countByDate.get(dates[dates.length - 2]) || 0;

  if (last > prev) return '<span class="trend-up" title="Rising">&#9650;</span>';
  if (last < prev) return '<span class="trend-down" title="Declining">&#9660;</span>';
  return '<span class="trend-dash" title="Stable">&mdash;</span>';
}

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
