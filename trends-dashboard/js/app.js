/**
 * app.js
 * Main entry point for the Trends Dashboard.
 * Imports all modules, loads data, populates the week selector,
 * renders every section, and manages global filter state.
 */

import { chartDefaults }          from './chart-utils.js';
import {
  loadAllData,
  buildTopicTimeSeries,
  mergeArrays,
  normalizeTopic,
  digestDate,
} from './data-loader.js';
import { renderWeeklySnapshot }   from './weekly-snapshot.js';
import { renderTopicHeatmap }     from './topic-heatmap.js';
import { renderTrendLines }       from './trend-lines.js';
import { renderAIEconomy }        from './ai-economy.js';
import { renderRegulatoryPulse }  from './regulatory-pulse.js';
import { renderLegalTechSignals } from './legal-tech-signals.js';
import { renderKeyVoices }        from './key-voices.js';
import { renderWeeklyDiff }       from './weekly-diff.js';

/* ------------------------------------------------------------------ */
/*  Global Filter State                                                */
/* ------------------------------------------------------------------ */

const state = {
  selectedTopic: null,
  selectedWeek: '__all__', // '__all__' or an index into state.data.digests
  data: null,
};

/**
 * Filter all sections to a specific topic (within the selected week).
 * Pass null or empty string to clear the filter.
 */
export function filterByTopic(topicName) {
  state.selectedTopic = topicName ? normalizeTopic(topicName) : null;
  updateFilterUI();
  rerender();
}

/**
 * The data every section should render: the selected week (or all weeks),
 * narrowed to the selected topic if one is set.
 */
function currentView() {
  if (!state.data) return null;
  let view = state.data;
  if (state.selectedWeek !== '__all__') {
    const digest = (state.data.digests || [])[Number(state.selectedWeek)];
    if (digest) view = buildSingleDigestView(digest, state.data);
  }
  return state.selectedTopic ? filterData(view, state.selectedTopic) : view;
}

function rerender() {
  const view = currentView();
  if (view) renderAllSections(view);
}

// Expose globally so other modules (e.g. topic-heatmap click handler) can call it
window.filterByTopic = filterByTopic;

/* ------------------------------------------------------------------ */
/*  Bootstrap                                                          */
/* ------------------------------------------------------------------ */

document.addEventListener('DOMContentLoaded', async () => {
  /* ---- 0. Theme ---- */
  initTheme();

  /* ---- 1. Chart.js global defaults ---- */
  applyChartDefaults();

  /* ---- 2. Show loading state ---- */
  showLoading(true);

  /* ---- 3. Section nav ---- */
  initSectionNav();

  /* ---- 4. Load data ---- */
  try {
    const dataBasePath = detectDataPath();
    const data = await loadAllData(dataBasePath);
    state.data = data;

    /* ---- 5. Populate week selector ---- */
    populateWeekSelector(data);

    /* ---- 6. Render everything ---- */
    renderAllSections(data);

    /* ---- 7. Populate meta bar ---- */
    updateMetaBar(data);
  } catch (err) {
    console.error('Dashboard failed to load:', err);
  } finally {
    /* ---- 8. Done (never leave the overlay up) ---- */
    showLoading(false);
  }
});

/* ------------------------------------------------------------------ */
/*  Theme Toggle                                                       */
/* ------------------------------------------------------------------ */

function readSetting(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function writeSetting(key, value) {
  try { localStorage.setItem(key, value); } catch { /* storage unavailable */ }
}

function initTheme() {
  const saved = readSetting('dashboard-theme');
  if (saved === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
  updateThemeIcon();

  const btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.addEventListener('click', () => {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      if (isDark) {
        document.documentElement.removeAttribute('data-theme');
        writeSetting('dashboard-theme', 'light');
      } else {
        document.documentElement.setAttribute('data-theme', 'dark');
        writeSetting('dashboard-theme', 'dark');
      }
      updateThemeIcon();
      applyChartDefaults();
      // Re-render charts with new theme colors, keeping week/topic filters
      rerender();
    });
  }
}

function updateThemeIcon() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  btn.textContent = isDark ? '\u2600' : '\u263E';
}

function applyChartDefaults() {
  chartDefaults();
  if (typeof Chart !== 'undefined') {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    Chart.defaults.color = isDark ? '#cbd5e1' : '#334155';
    Chart.defaults.scale.grid = {
      color: isDark ? 'rgba(148, 163, 184, 0.12)' : 'rgba(100, 116, 139, 0.12)',
    };
    Chart.defaults.plugins.tooltip.backgroundColor = isDark ? '#0f172a' : '#1e1b4b';
  }
}

/* ------------------------------------------------------------------ */
/*  Section Navigation                                                 */
/* ------------------------------------------------------------------ */

function initSectionNav() {
  const navLinks = document.querySelectorAll('.nav-pill');
  if (navLinks.length === 0) return;

  // Smooth scroll on click
  navLinks.forEach((link) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const target = document.querySelector(link.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // Highlight active section on scroll
  const sections = [...navLinks].map((l) => document.querySelector(l.getAttribute('href'))).filter(Boolean);
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          navLinks.forEach((l) => l.classList.remove('active'));
          const activeLink = document.querySelector(`.nav-pill[href="#${entry.target.id}"]`);
          if (activeLink) activeLink.classList.add('active');
        }
      }
    },
    { rootMargin: '-20% 0px -70% 0px' }
  );
  sections.forEach((s) => observer.observe(s));
}

/* ------------------------------------------------------------------ */
/*  Render All Sections                                                */
/* ------------------------------------------------------------------ */

const SECTIONS = [
  ['section-weekly-snapshot',    (el, data) => renderWeeklySnapshot(el, data)],
  ['section-topic-heatmap',      (el, data) => renderTopicHeatmap(el, data)],
  ['section-weekly-diff',        (el, data) => renderWeeklyDiff(el, data)],
  ['section-trend-lines',        (el, data) => renderTrendLines(el, 'trend-lines-chart', data)],
  ['section-ai-economy',         (el, data) => renderAIEconomy(el, data)],
  ['section-regulatory-pulse',   (el, data) => renderRegulatoryPulse(el, data)],
  ['section-legal-tech-signals', (el, data) => renderLegalTechSignals(el, data)],
  ['section-key-voices',         (el, data) => renderKeyVoices(el, data)],
];

/**
 * Render every section. Each one is isolated so a failure in one (for
 * example Chart.js failing to load from the CDN) cannot blank the rest.
 */
function renderAllSections(data) {
  const view = { ...data, selectedTopic: state.selectedTopic };
  for (const [id, render] of SECTIONS) {
    const el = document.getElementById(id);
    if (!el) continue;
    try {
      render(el, view);
    } catch (err) {
      console.error(`Failed to render ${id}:`, err);
    }
  }
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

  const allOpt = document.createElement('option');
  allOpt.value = '__all__';
  allOpt.textContent = 'All Weeks';
  selector.appendChild(allOpt);

  digests.forEach((d, i) => {
    const labelDate = d?.meta?.date_range_start || digestDate(d);
    const opt = document.createElement('option');
    opt.value = String(i);
    opt.textContent = formatWeekLabel(labelDate);
    selector.appendChild(opt);
  });

  selector.addEventListener('change', () => {
    state.selectedWeek = selector.value;
    rerender();
  });
}

function buildSingleDigestView(digest, fullData) {
  const digests = [digest];
  return {
    index: fullData.index,
    digests,
    latest: digest,
    topicTimeSeries:      buildTopicTimeSeries(digests),
    aggregatedEconomy:    mergeArrays(digests, 'ai_economy_events'),
    aggregatedRegulatory: mergeArrays(digests, 'regulatory_events'),
    aggregatedLegalTech:  mergeArrays(digests, 'legal_tech_signals'),
    aggregatedSources:    mergeArrays(digests, 'source_contributions'),
    trendAnalysis: { emerging: [], fading: [] },
  };
}

/* ------------------------------------------------------------------ */
/*  Topic Filtering                                                    */
/* ------------------------------------------------------------------ */

const normText = (v) => String(v || '').toLowerCase().replace(/\s+/g, ' ').trim();
const normCategory = (v) => normText(v).replace(/ /g, '_');

function itemTopics(item) {
  const list = item.top_topics || item.topics || [];
  return (Array.isArray(list) ? list : [])
    .map((t) => normalizeTopic(typeof t === 'string' ? t : t?.name || t?.topic || ''));
}

/**
 * Narrow the section data to one topic. Digest events carry no topic field,
 * so matching uses what the data does link:
 *   - sources: their top_topics include the topic;
 *   - regulatory events: impact_area names the topic (or its category);
 *   - economy / legal-tech events: the headline matches one of the topic's
 *     representative headlines, or the event's source covered the topic in
 *     the same digest.
 * Snapshot, heatmap and trend lines keep their full data (the heatmap marks
 * the selected row) so the page never goes blank.
 */
function filterData(data, topicName) {
  const topic = normalizeTopic(topicName);
  const byDate = new Map();
  const categories = new Set();

  for (const d of data.digests || []) {
    const ctx = { headlines: [], sources: new Set() };
    for (const t of d.topics || []) {
      if (normalizeTopic(t.name || t.topic || '') !== topic) continue;
      if (t.category) categories.add(normCategory(t.category));
      for (const h of t.representative_headlines || []) ctx.headlines.push(normText(h));
    }
    for (const s of d.source_contributions || []) {
      if (itemTopics(s).includes(topic)) {
        ctx.sources.add(normText(s.source_name || s.source || s.name));
      }
    }
    byDate.set(digestDate(d), ctx);
  }

  const headlineMatches = (item) => {
    const ctx = byDate.get(item._digestDate);
    const text = normText(item.headline || item.title || item.description);
    return Boolean(ctx && text && ctx.headlines.some(
      (h) => h && (h.includes(text) || text.includes(h))));
  };
  const sourceCovers = (item) => {
    const ctx = byDate.get(item._digestDate);
    return Boolean(ctx && ctx.sources.has(normText(item.source || item.source_name)));
  };
  const impactMatches = (item) => {
    const areas = Array.isArray(item.impact_area) ? item.impact_area : [item.impact_area];
    return areas.filter(Boolean).some(
      (a) => normalizeTopic(a) === topic || categories.has(normCategory(a)));
  };

  return {
    ...data,
    aggregatedEconomy:    (data.aggregatedEconomy || []).filter((e) => headlineMatches(e) || sourceCovers(e)),
    aggregatedRegulatory: (data.aggregatedRegulatory || []).filter((e) => impactMatches(e) || headlineMatches(e)),
    aggregatedLegalTech:  (data.aggregatedLegalTech || []).filter((e) => headlineMatches(e) || sourceCovers(e)),
    aggregatedSources:    (data.aggregatedSources || []).filter((s) => itemTopics(s).includes(topic)),
  };
}

function updateFilterUI() {
  const badge = document.getElementById('active-filter');
  if (!badge) return;

  if (state.selectedTopic) {
    badge.textContent = `Filtered: ${state.selectedTopic}`;
    badge.style.display = 'inline-flex';
    badge.title = 'Clear topic filter';
    badge.onclick = () => filterByTopic(null);
  } else {
    badge.style.display = 'none';
  }
}

/* ------------------------------------------------------------------ */
/*  Meta Bar & Loading                                                 */
/* ------------------------------------------------------------------ */

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

  if (runDate) document.getElementById('meta-last-updated').textContent = `Updated ${runDate}`;
  if (rangeStart && rangeEnd) document.getElementById('meta-digest-range').textContent = `${rangeStart} \u2013 ${rangeEnd}`;
  if (sourceCount) document.getElementById('meta-sources').textContent = `${sourceCount} sources`;
  if (articleCount) {
    document.getElementById('meta-articles').textContent =
      `${articleCount} items \u00B7 ${digestCount} digest${digestCount !== 1 ? 's' : ''}`;
  }

  bar.style.display = 'flex';
}

function showLoading(show) {
  const loader = document.getElementById('loading-overlay');
  if (loader) loader.style.display = show ? 'flex' : 'none';
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function detectDataPath() {
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
