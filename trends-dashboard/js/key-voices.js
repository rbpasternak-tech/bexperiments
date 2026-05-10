/**
 * key-voices.js
 * Renders the Key Voices section:
 *   - Chart.js radar chart: top 6 sources, axes = topic categories
 *   - Sortable HTML table: source name, article count, signal strength badge, top topics
 */

import { COLORS, colorForCategory, formatNumber, esc, capitalize, emptyState } from './chart-utils.js';

/* ---- Module-level chart reference ---- */
let radarChartInstance = null;

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

/**
 * @param {HTMLElement} container
 * @param {Object}      data — full dashboard data (uses data.aggregatedSources, data.digests)
 */
export function renderKeyVoices(container, data) {
  const sources = data.aggregatedSources || [];

  if (sources.length === 0) {
    container.innerHTML = emptyState('Key Voices');
    return;
  }

  /* ---- Build source profiles ---- */
  const profiles = buildSourceProfiles(sources, data.digests || []);
  const topProfiles = profiles.slice(0, 20);
  const radarProfiles = profiles.slice(0, 6);

  /* ---- Collect all category axes for radar ---- */
  const categorySet = new Set();
  for (const p of radarProfiles) {
    for (const cat of Object.keys(p.categoryCounts)) {
      categorySet.add(cat);
    }
  }
  const categories = [...categorySet].sort();

  /* ---- Build HTML ---- */
  let html = '<h2 class="section-title">Key Voices</h2>';

  html += '<div class="voices-layout">';

  // Radar chart
  if (radarProfiles.length >= 2 && categories.length >= 3) {
    html += `<div class="voices-chart-col">
      <h3 class="subsection-title">Source Coverage by Topic</h3>
      <div class="chart-container" style="position:relative;height:360px;">
        <canvas id="key-voices-radar"></canvas>
      </div>
    </div>`;
  }

  // Table
  html += '<div class="voices-table-col">';
  html += '<h3 class="subsection-title">Source Ranking</h3>';
  html += renderTable(topProfiles);
  html += '</div>';

  html += '</div>'; // .voices-layout

  container.innerHTML = html;

  /* ---- Render radar chart ---- */
  if (radarProfiles.length >= 2 && categories.length >= 3) {
    renderRadar(radarProfiles, categories);
  }

  /* ---- Wire up sorting ---- */
  wireTableSort(container);
}

/* ------------------------------------------------------------------ */
/*  Source Profile Builder                                              */
/* ------------------------------------------------------------------ */

function buildSourceProfiles(sourcesArray, digests) {
  // Build a topic name -> category map from all digests
  const topicCategoryMap = new Map();
  for (const d of digests) {
    for (const t of d.topics || []) {
      const name = t.name || t.topic || '';
      const cat = (t.category || '').toLowerCase().replace(/\s+/g, '_');
      if (name && cat) topicCategoryMap.set(name, cat);
    }
  }

  // Aggregate: source name -> { total articles, category counts, top topics }
  const map = new Map();

  for (const s of sourcesArray) {
    const name = s.source_name || s.source || s.name || 'Unknown';
    if (!map.has(name)) {
      map.set(name, {
        name,
        totalArticles: 0,
        categoryCounts: {},
        topTopics: new Set(),
      });
    }
    const profile = map.get(name);
    const articles = s.article_count || s.count || 1;
    profile.totalArticles += articles;

    // Derive category counts from top_topics via the topic->category map
    const topics = s.topics || s.top_topics || [];
    if (Array.isArray(topics)) {
      for (const t of topics) {
        const topicName = typeof t === 'string' ? t : t.name || t.topic || '';
        profile.topTopics.add(topicName);
        const cat = topicCategoryMap.get(topicName) || (s.category || s.topic || '').toLowerCase().replace(/\s+/g, '_');
        if (cat) {
          profile.categoryCounts[cat] = (profile.categoryCounts[cat] || 0) + 1;
        }
      }
    }
  }

  // Also scan digests for source_contributions to capture additional topic info
  for (const d of digests) {
    const contributions = d.source_contributions || [];
    for (const c of contributions) {
      const name = c.source_name || c.source || c.name || 'Unknown';
      if (!map.has(name)) continue;
      const profile = map.get(name);
      const topics = c.topics || c.top_topics || [];
      if (Array.isArray(topics)) {
        for (const t of topics) {
          const topicName = typeof t === 'string' ? t : t.name || t.topic || '';
          profile.topTopics.add(topicName);
          const cat = topicCategoryMap.get(topicName);
          if (cat) {
            profile.categoryCounts[cat] = (profile.categoryCounts[cat] || 0) + 1;
          }
        }
      }
    }
  }

  return [...map.values()]
    .sort((a, b) => b.totalArticles - a.totalArticles)
    .map((p) => ({
      ...p,
      topTopics: [...p.topTopics].filter(Boolean).slice(0, 5),
      signalStrength: signalStrength(p.totalArticles),
    }));
}

function signalStrength(count) {
  if (count >= 20) return { label: 'Very High', cls: 'signal-very-high' };
  if (count >= 10) return { label: 'High',      cls: 'signal-high' };
  if (count >= 5)  return { label: 'Medium',    cls: 'signal-medium' };
  return              { label: 'Low',       cls: 'signal-low' };
}

/* ------------------------------------------------------------------ */
/*  Radar Chart                                                        */
/* ------------------------------------------------------------------ */

function renderRadar(profiles, categories) {
  const ctx = document.getElementById('key-voices-radar');
  if (!ctx) return;

  const radarColors = [
    '#4F46E5', '#7C3AED', '#2563EB',
    '#059669', '#DC2626', '#D97706',
  ];

  const datasets = profiles.map((p, i) => {
    const color = radarColors[i % radarColors.length];
    return {
      label: p.name,
      data: categories.map((cat) => p.categoryCounts[cat] || 0),
      borderColor: color,
      backgroundColor: color + '22',
      pointBackgroundColor: color,
      pointBorderColor: '#fff',
      pointBorderWidth: 1,
    };
  });

  if (radarChartInstance) radarChartInstance.destroy();

  radarChartInstance = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: categories.map(capitalize),
      datasets,
    },
    options: {
      plugins: {
        legend: { position: 'bottom' },
      },
      scales: {
        r: {
          beginAtZero: true,
          ticks: { stepSize: 1 },
          pointLabels: { font: { size: 11 } },
        },
      },
    },
  });
}

/* ------------------------------------------------------------------ */
/*  HTML Table                                                         */
/* ------------------------------------------------------------------ */

function renderTable(profiles) {
  let html = `
    <table class="voices-table" id="voices-table">
      <thead>
        <tr>
          <th data-sort="name" class="sortable">Source</th>
          <th data-sort="total" class="sortable">Articles</th>
          <th data-sort="signal" class="sortable">Signal Strength</th>
          <th>Top Topics</th>
        </tr>
      </thead>
      <tbody>`;

  for (const p of profiles) {
    const topicsHtml = p.topTopics
      .map((t) => `<span class="topic-chip">${esc(t)}</span>`)
      .join(' ');

    html += `
      <tr data-name="${esc(p.name)}" data-total="${p.totalArticles}" data-signal="${p.signalStrength.label}">
        <td class="source-cell">${esc(p.name)}</td>
        <td class="articles-cell">${formatNumber(p.totalArticles)}</td>
        <td><span class="signal-badge ${p.signalStrength.cls}">${p.signalStrength.label}</span></td>
        <td class="topics-cell">${topicsHtml || '<span class="no-data-inline">--</span>'}</td>
      </tr>`;
  }

  html += '</tbody></table>';
  return html;
}

/* ------------------------------------------------------------------ */
/*  Table Sorting                                                      */
/* ------------------------------------------------------------------ */

function wireTableSort(container) {
  const table = container.querySelector('#voices-table');
  if (!table) return;

  const headers = table.querySelectorAll('th.sortable');
  headers.forEach((th) => {
    th.style.cursor = 'pointer';
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      const tbody = table.querySelector('tbody');
      const rows = [...tbody.querySelectorAll('tr')];

      // Toggle direction
      const asc = th.classList.toggle('sort-asc');
      headers.forEach((h) => { if (h !== th) h.classList.remove('sort-asc'); });

      rows.sort((a, b) => {
        let va, vb;
        if (key === 'total') {
          va = parseInt(a.dataset.total, 10) || 0;
          vb = parseInt(b.dataset.total, 10) || 0;
          return asc ? va - vb : vb - va;
        }
        if (key === 'signal') {
          const order = { 'Very High': 4, 'High': 3, 'Medium': 2, 'Low': 1 };
          va = order[a.dataset.signal] || 0;
          vb = order[b.dataset.signal] || 0;
          return asc ? va - vb : vb - va;
        }
        // name
        va = (a.dataset.name || '').toLowerCase();
        vb = (b.dataset.name || '').toLowerCase();
        return asc ? va.localeCompare(vb) : vb.localeCompare(va);
      });

      for (const row of rows) tbody.appendChild(row);
    });
  });
}

