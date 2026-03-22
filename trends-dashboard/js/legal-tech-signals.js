/**
 * legal-tech-signals.js
 * Renders the Legal Tech Signals section:
 *   - Count cards by signal type
 *   - Entity ranking (sorted by mentions)
 *   - Chronological signal feed with type badges and source links
 */

import { formatNumber } from './chart-utils.js';

/* ---- Signal type styling ---- */
const SIGNAL_TYPE_COLORS = {
  product_launch: '#22C55E',
  firm_adoption:  '#3B82F6',
  integration:    '#8B5CF6',
  milestone:      '#F59E0B',
};

const SIGNAL_TYPE_LABELS = {
  product_launch: 'Product Launch',
  firm_adoption:  'Firm Adoption',
  integration:    'Integration',
  milestone:      'Milestone',
};

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

/**
 * @param {HTMLElement} container
 * @param {Object}      data — full dashboard data (uses data.aggregatedLegalTech)
 */
export function renderLegalTechSignals(container, data) {
  const signals = data.aggregatedLegalTech || [];

  if (signals.length === 0) {
    container.innerHTML = emptyState('Legal Tech Signals');
    return;
  }

  /* ---- Compute counts by type and entity ranking ---- */
  const typeCounts = {};
  const entityCounts = {};

  for (const sig of signals) {
    const type = (sig.type || sig.signal_type || 'other').toLowerCase();
    typeCounts[type] = (typeCounts[type] || 0) + 1;

    const entity = sig.entity || sig.company || sig.organization || '';
    if (entity) {
      entityCounts[entity] = (entityCounts[entity] || 0) + 1;
    }
  }

  const entityRanking = Object.entries(entityCounts)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 15);

  /* ---- Build HTML ---- */
  let html = '<h2 class="section-title">Legal Tech Signals</h2>';

  // Count cards
  html += '<div class="quick-stats">';
  for (const [type, count] of Object.entries(typeCounts).sort(([, a], [, b]) => b - a)) {
    const label = SIGNAL_TYPE_LABELS[type] || capitalize(type);
    const color = SIGNAL_TYPE_COLORS[type] || '#6366F1';
    html += `
      <div class="stat-card" style="border-top:3px solid ${color}">
        <span class="stat-label">${esc(label)}</span>
        <span class="stat-value">${formatNumber(count)}</span>
      </div>`;
  }
  html += '</div>';

  // Two-column layout: entity ranking + signal feed
  html += '<div class="lts-columns">';

  // Entity ranking
  html += '<div class="lts-col lts-col-entities">';
  html += '<h3 class="subsection-title">Top Entities</h3>';
  if (entityRanking.length > 0) {
    html += '<ol class="entity-ranking">';
    for (const [entity, count] of entityRanking) {
      html += `<li class="entity-rank-item">
        <span class="entity-name">${esc(entity)}</span>
        <span class="entity-count">${count}</span>
      </li>`;
    }
    html += '</ol>';
  } else {
    html += '<p class="no-data-inline">No entity data</p>';
  }
  html += '</div>';

  // Signal feed
  html += '<div class="lts-col lts-col-feed">';
  html += '<h3 class="subsection-title">Signal Feed</h3>';
  html += '<div class="event-list">';
  for (const sig of signals.slice(0, 40)) {
    html += signalItem(sig);
  }
  html += '</div></div>';

  html += '</div>'; // .lts-columns

  container.innerHTML = html;
}

/* ------------------------------------------------------------------ */
/*  Signal Feed Item                                                   */
/* ------------------------------------------------------------------ */

function signalItem(sig) {
  const type     = (sig.type || sig.signal_type || 'signal').toLowerCase();
  const label    = SIGNAL_TYPE_LABELS[type] || capitalize(type);
  const color    = SIGNAL_TYPE_COLORS[type] || '#6366F1';
  const entity   = esc(sig.entity || sig.company || sig.organization || '');
  const headline = esc(sig.headline || sig.title || sig.description || '');
  const source   = renderSourceLink(sig);
  const date     = sig._digestDate || '';

  return `
    <div class="event-item signal-item">
      <span class="event-type-badge" style="background:${color}">${esc(label)}</span>
      ${date ? `<span class="event-date">${formatShortDate(date)}</span>` : ''}
      ${entity ? `<strong class="event-entity">${entity}</strong>` : ''}
      <span class="event-headline">${headline}</span>
      ${source}
    </div>`;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function renderSourceLink(sig) {
  const url = sig.source_url || sig.url || sig.link || '';
  const name = sig.source || sig.source_name || '';
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

function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, ' ');
}

function formatShortDate(dateStr) {
  try {
    const dateOnly = String(dateStr).slice(0, 10);
    const d = new Date(dateOnly + 'T00:00:00');
    if (isNaN(d)) return dateStr;
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
