/**
 * app.js
 * Main entry point for the Trends Dashboard.
 * Imports all modules, loads data, populates the week selector,
 * renders every section, and manages global filter state.
 */

import { chartDefaults }          from './chart-utils.js';
import { loadAllData }            from './data-loader.js';
import { renderWeeklySnapshot }   from './weekly-snapshot.js';
import { renderTopicHeatmap }     from './topic-heatmap.js';
import { renderTrendLines }       from './trend-lines.js';
import { renderAIEconomy }        from './ai-economy.js';
import { renderRegulatoryPulse }  from './regulatory-pulse.js';
import { renderLegalTechSignals } from './legal-tech-signals.js';
import { renderKeyVoices }        from './key-voices.js';

/* ------------------------------------------------------------------ */
/*  Global Filter State                                                */
/* ------------------------------------------------------------------ */

const state = {
  selectedTopic: null,
  data: null,
};

/**
 * Filter all sections to a specific topic.
 * Pass null or empty string to clear the filter.
 */
export function filterByTopic(topicName) {
  state.selectedTopic = topicName || null;
  updateFilterUI();

  // Re-render sections that respond to topic filtering
  if (state.data) {
    const filtered = topicName ? filterData(state.data, topicName) : state.data;
    renderAllSections(filtered);
  }
}

// Expose globally so other modules (e.g. topic-heatmap click handler) can call it
window.filterByTopic = filterByTopic;

/* ------------------------------------------------------------------ */
/*  Bootstrap                                                          */
/* ------------------------------------------------------------------ */

document.addEventListener('DOMContentLoaded', async () => {
  /* ---- 1. Chart.js global defaults ---- */
  chartDefaults();

  /* ---- 2. Show loading state ---- */
  showLoading(true);

  /* ---- 3. Load data ---- */
  const dataBasePath = detectDataPath();
  const data = await loadAllData(dataBasePath);
  state.data = data;

  /* ---- 4. Populate week selector ---- */
  populateWeekSelector(data);

  /* ---- 5. Render everything ---- */
  renderAllSections(data);

  /* ---- 6. Populate meta bar ---- */
  updateMetaBar(data);

  /* ---- 7. Done ---- */
  showLoading(false);
});

/* ------------------------------------------------------------------ */
/*  Render All Sections                                                */
/* ------------------------------------------------------------------ */

function renderAllSections(data) {
  const section = (id) => document.getElementById(id);

  const snapshotEl   = section('section-weekly-snapshot');
  const heatmapEl    = section('section-topic-heatmap');
  const trendEl      = section('section-trend-lines');
  const economyEl    = section('section-ai-economy');
  const regulatoryEl = section('section-regulatory-pulse');
  const legalTechEl  = section('section-legal-tech-signals');
  const voicesEl     = section('section-key-voices');

  if (snapshotEl)   renderWeeklySnapshot(snapshotEl, data);
  if (heatmapEl)    renderTopicHeatmap(heatmapEl, data);
  if (trendEl)      renderTrendLines(trendEl, 'trend-lines-chart', data);
  if (economyEl)    renderAIEconomy(economyEl, data);
  if (regulatoryEl) renderRegulatoryPulse(regulatoryEl, data);
  if (legalTechEl)  renderLegalTechSignals(legalTechEl, data);
  if (voicesEl)     renderKeyVoices(voicesEl, data);
}

/* ------------------------------------------------------------------ */
/*  Week Selector                                                      */
/* ------------------------------------------------------------------ */

function populateWeekSelector(data) {
  const selector = document.getElementById('week-selector');
  if (!selector) return;

  const digests = data.digests || [];
  if (digests.length === 0) {
    selector.innerHTML = '<option>No digests available</option>';
    return;
  }

  selector.innerHTML = '';

  // "All weeks" option
  const allOpt = document.createElement('option');
  allOpt.value = '__all__';
  allOpt.textContent = 'All Weeks';
  selector.appendChild(allOpt);

  for (const d of digests) {
    const date = d?.meta?.run_date || d?.meta?.date || d?.meta?.week_ending || d?.date || 'unknown';
    const labelDate = d?.meta?.date_range_start || date;
    const opt = document.createElement('option');
    opt.value = date;
    opt.textContent = formatWeekLabel(labelDate);
    selector.appendChild(opt);
  }

  // Event listener
  selector.addEventListener('change', () => {
    const val = selector.value;
    if (val === '__all__') {
      renderAllSections(state.data);
    } else {
      // Find the specific digest and create a single-digest data view
      const digest = digests.find((d) => {
        const dd = d?.meta?.run_date || d?.meta?.date || d?.meta?.week_ending || d?.date || '';
        return dd === val;
      });
      if (digest) {
        const singleView = buildSingleDigestView(digest, state.data);
        renderAllSections(singleView);
      }
    }
  });
}

/**
 * Build a data object scoped to a single digest, reusing the same shape
 * that loadAllData() returns.
 */
function buildSingleDigestView(digest, fullData) {
  // Re-use data-loader helpers inline
  const { buildTopicTimeSeries, computeTrends, mergeArrays } = fullData._helpers || {};

  // Simplified single-digest view
  return {
    index: fullData.index,
    digests: [digest],
    latest: digest,
    topicTimeSeries: buildTopicTimeSeriesInline([digest]),
    aggregatedEconomy:    tagArray(digest.ai_economy_events || [], digest),
    aggregatedRegulatory: tagArray(digest.regulatory_events || [], digest),
    aggregatedLegalTech:  tagArray(digest.legal_tech_signals || [], digest),
    aggregatedSources:    tagArray(digest.source_contributions || [], digest),
    trendAnalysis: { emerging: [], fading: [] },
  };
}

function tagArray(arr, digest) {
  const date = digest?.meta?.run_date || digest?.meta?.date || digest?.meta?.week_ending || digest?.date || '';
  return arr.map((item) => ({ ...item, _digestDate: date }));
}

function buildTopicTimeSeriesInline(digests) {
  const topicMap = new Map();
  for (const d of digests) {
    const date = d?.meta?.run_date || d?.meta?.date || d?.meta?.week_ending || d?.date || 'unknown';
    for (const t of d.topics || []) {
      const name = t.name || t.topic || 'Unknown';
      if (!topicMap.has(name)) topicMap.set(name, []);
      topicMap.get(name).push({ date, count: t.mention_count ?? t.count ?? 1 });
    }
  }
  return [...topicMap.entries()].map(([topic, series]) => ({ topic, series }));
}

/* ------------------------------------------------------------------ */
/*  Topic Filtering                                                    */
/* ------------------------------------------------------------------ */

/**
 * Create a filtered copy of data where only events/signals matching
 * the given topic name are included.
 */
function filterData(data, topicName) {
  const lower = topicName.toLowerCase();

  const matchesTopic = (item) => {
    const fields = [
      item.topic, item.category, item.sector,
      ...(item.topics || []).map((t) => typeof t === 'string' ? t : t.name || t.topic || ''),
    ];
    return fields.some((f) => f && f.toLowerCase().includes(lower));
  };

  return {
    ...data,
    // Keep full time series (chart still shows all, but highlight is visual)
    topicTimeSeries: data.topicTimeSeries,
    aggregatedEconomy:    data.aggregatedEconomy.filter(matchesTopic),
    aggregatedRegulatory: data.aggregatedRegulatory.filter(matchesTopic),
    aggregatedLegalTech:  data.aggregatedLegalTech.filter(matchesTopic),
    aggregatedSources:    data.aggregatedSources.filter(matchesTopic),
    trendAnalysis: data.trendAnalysis,
  };
}

function updateFilterUI() {
  const badge = document.getElementById('active-filter');
  if (!badge) return;

  if (state.selectedTopic) {
    badge.textContent = `Filtered: ${state.selectedTopic}`;
    badge.style.display = 'inline-flex';
    badge.onclick = () => filterByTopic(null);
  } else {
    badge.style.display = 'none';
  }
}

/* ------------------------------------------------------------------ */
/*  Loading State                                                      */
/* ------------------------------------------------------------------ */

/**
 * Populate the data meta bar with last-updated info from the latest digest.
 * @param {Object} data
 */
function updateMetaBar(data) {
  const bar = document.getElementById('data-meta-bar');
  if (!bar || !data.latest) return;

  const meta = data.latest.meta || {};

  const runDate = meta.run_date
    ? new Date(meta.run_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : null;

  const rangeStart = meta.date_range_start
    ? new Date(meta.date_range_start + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : null;
  const rangeEnd = meta.date_range_end
    ? new Date(meta.date_range_end + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : null;

  const sourceCount = Array.isArray(meta.sources_analyzed) ? meta.sources_analyzed.length : null;
  const articleCount = (meta.newsletter_count || 0) + (meta.rss_article_count || 0);
  const digestCount = (data.digests || []).length;

  if (runDate) {
    document.getElementById('meta-last-updated').textContent = `Updated ${runDate}`;
  }
  if (rangeStart && rangeEnd) {
    document.getElementById('meta-digest-range').textContent = `${rangeStart} – ${rangeEnd}`;
  }
  if (sourceCount) {
    document.getElementById('meta-sources').textContent = `${sourceCount} sources`;
  }
  if (articleCount) {
    document.getElementById('meta-articles').textContent =
      `${articleCount} items · ${digestCount} digest${digestCount !== 1 ? 's' : ''}`;
  }

  bar.style.display = 'flex';
}

function showLoading(show) {
  const loader = document.getElementById('loading-overlay');
  if (loader) {
    loader.style.display = show ? 'flex' : 'none';
  }
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function detectDataPath() {
  // Support running from subdirectory (e.g., GitHub Pages)
  const base = document.querySelector('base')?.href || '';
  if (base && base.includes('/trends-dashboard/')) {
    return 'data';
  }
  return 'data';
}

function formatWeekLabel(dateStr) {
  try {
    const dateOnly = String(dateStr).slice(0, 10);
    const d = new Date(dateOnly + 'T00:00:00');
    if (isNaN(d)) return dateStr;
    return `Week of ${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`;
  } catch {
    return dateStr;
  }
}
