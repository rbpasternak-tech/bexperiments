/**
 * weekly-snapshot.js
 * Renders the Weekly Snapshot section: top stories, one-to-watch, and quick stats.
 */

import { SENTIMENT_COLORS, formatCurrency, formatNumber, esc, emptyState } from './chart-utils.js';

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

/**
 * @param {HTMLElement} container — the section element to render into
 * @param {Object}      data     — full dashboard data (uses data.latest, data.digests)
 */
export function renderWeeklySnapshot(container, data) {
  const digest = data.latest;
  if (!digest || !digest.weekly_snapshot) {
    container.innerHTML = emptyState('Weekly Snapshot');
    return;
  }

  const snap = digest.weekly_snapshot;
  const stories = (snap.top_stories || []).slice(0, 3);
  const oneToWatch = snap.one_to_watch;
  const stats = snap.quick_stats || {};

  // Find previous digest for WoW comparison (digests sorted newest-first)
  const digests = data.digests || [];
  const prevDigest = digests.length > 1 ? digests[1] : null;
  const prevStats = prevDigest?.weekly_snapshot?.quick_stats || null;

  let html = '<h2 class="section-title">Weekly Snapshot</h2>';

  /* ---- Weekly Narrative ---- */
  const narrative = digest.weekly_narrative || snap.narrative || '';
  if (narrative) {
    html += `<p class="weekly-narrative">${esc(narrative)}</p>`;
  }

  /* ---- Top Stories ---- */
  html += '<div class="story-grid">';
  for (let i = 0; i < stories.length; i++) {
    html += storyCard(stories[i], i + 1);
  }

  /* ---- One to Watch ---- */
  if (oneToWatch) {
    html += oneToWatchCard(oneToWatch);
  }
  html += '</div>'; // .story-grid

  /* ---- Quick Stats ---- */
  html += quickStatsRow(stats, prevStats, digest);

  container.innerHTML = html;
}

/* ------------------------------------------------------------------ */
/*  Story Cards                                                        */
/* ------------------------------------------------------------------ */

function storyCard(story, rank) {
  const headline = esc(story.headline || story.title || 'Untitled');
  const why = esc(story.why_it_matters || story.summary || '');
  const sources = renderSourceLinks(story.sources || story.source_links || []);

  return `
    <div class="card story-card">
      <span class="story-rank">#${rank}</span>
      <h3 class="story-headline">${headline}</h3>
      ${why ? `<p class="story-why">${why}</p>` : ''}
      ${sources ? `<div class="story-sources">${sources}</div>` : ''}
    </div>`;
}

function oneToWatchCard(item) {
  const title = esc(item.headline || item.title || item.name || 'One to Watch');
  const desc = esc(item.why_it_matters || item.description || item.summary || '');
  const sources = renderSourceLinks(item.sources || item.source_links || []);

  return `
    <div class="card story-card one-to-watch">
      <span class="story-rank otw-badge">One to Watch</span>
      <h3 class="story-headline">${title}</h3>
      ${desc ? `<p class="story-why">${desc}</p>` : ''}
      ${sources ? `<div class="story-sources">${sources}</div>` : ''}
    </div>`;
}

/* ------------------------------------------------------------------ */
/*  Quick Stats Row                                                    */
/* ------------------------------------------------------------------ */

/**
 * Compute week-over-week percentage change between two numeric values.
 * Returns null if comparison is not meaningful.
 * @param {number} current
 * @param {number} prev
 * @returns {{pct: number, html: string}|null}
 */
function wowChange(current, prev) {
  if (prev == null || prev === 0) return null;
  const pct = Math.round(((current - prev) / prev) * 100);
  if (Math.abs(pct) < 2) return null; // ignore noise
  const cls = pct > 0 ? 'wow-up' : 'wow-down';
  const arrow = pct > 0 ? '↑' : '↓';
  return { pct, html: `<span class="wow-badge ${cls}">${arrow} ${Math.abs(pct)}%</span>` };
}

function quickStatsRow(stats, prevStats, digest) {
  const totalArticles   = stats.total_articles_analyzed ?? stats.total_articles ?? stats.article_count ?? 0;
  const fundingTotal    = stats.funding_total_usd ?? stats.funding_total ?? stats.total_funding ?? 0;
  const regulationCount = stats.new_regulations_count ?? stats.regulations_count ?? stats.regulation_count ?? 0;
  const launches        = stats.product_launches_count ?? stats.product_launches ?? stats.launch_count ?? 0;
  const dominantTopic   = stats.dominant_topic ?? stats.top_topic ?? '';
  const sentimentDist   = stats.sentiment_balance ?? stats.sentiment_distribution ?? stats.sentiment ?? null;

  // Previous stats for WoW
  const prevArticles   = prevStats ? (prevStats.total_articles_analyzed ?? prevStats.total_articles ?? 0) : null;
  const prevFunding    = prevStats ? (prevStats.funding_total_usd ?? prevStats.funding_total ?? 0) : null;
  const prevRegCount   = prevStats ? (prevStats.new_regulations_count ?? prevStats.regulations_count ?? 0) : null;
  const prevLaunches   = prevStats ? (prevStats.product_launches_count ?? prevStats.product_launches ?? 0) : null;

  const wowArticles = wowChange(totalArticles, prevArticles);
  const wowFunding  = wowChange(fundingTotal, prevFunding);
  const wowRegs     = wowChange(regulationCount, prevRegCount);
  const wowLaunches = wowChange(launches, prevLaunches);

  let html = '<div class="quick-stats">';

  html += statCard('Articles', formatNumber(totalArticles) + (wowArticles?.html || ''), 'article-count');
  html += statCard('Funding', formatCurrency(fundingTotal) + (wowFunding?.html || ''), 'funding-total');
  html += statCard('Regulations', formatNumber(regulationCount) + (wowRegs?.html || ''), 'regulation-count');
  html += statCard('Launches', formatNumber(launches) + (wowLaunches?.html || ''), 'launch-count');

  if (dominantTopic) {
    html += `
      <div class="stat-card dominant-topic">
        <span class="stat-label">Dominant Topic</span>
        <span class="stat-value badge">${esc(dominantTopic)}</span>
      </div>`;
  }

  /* ---- Sentiment Bar ---- */
  if (sentimentDist && typeof sentimentDist === 'object') {
    html += sentimentBar(sentimentDist);
  }

  html += '</div>'; // .quick-stats
  return html;
}

function statCard(label, value, cls = '') {
  return `
    <div class="stat-card ${cls}">
      <span class="stat-label">${label}</span>
      <span class="stat-value">${value}</span>
    </div>`;
}

/* ------------------------------------------------------------------ */
/*  Sentiment Bar                                                      */
/* ------------------------------------------------------------------ */

function sentimentBar(dist) {
  const entries = Object.entries(dist).filter(([, v]) => v > 0);
  if (entries.length === 0) return '';

  const total = entries.reduce((s, [, v]) => s + v, 0);
  if (total === 0) return '';

  let segments = '';
  for (const [key, val] of entries) {
    const pct = ((val / total) * 100).toFixed(1);
    const color = SENTIMENT_COLORS[key] || '#94A3B8';
    segments += `<div class="sentiment-segment" style="width:${pct}%;background:${color}" title="${esc(key)}: ${pct}%"></div>`;
  }

  return `
    <div class="stat-card sentiment-bar-card">
      <span class="stat-label">Sentiment</span>
      <div class="sentiment-bar">${segments}</div>
      <div class="sentiment-legend">
        ${entries.map(([k]) => `<span class="legend-dot" style="background:${SENTIMENT_COLORS[k] || '#94A3B8'}"></span><span class="legend-label">${esc(k)}</span>`).join(' ')}
      </div>
    </div>`;
}

function renderSourceLinks(sources) {
  if (!sources || sources.length === 0) return '';
  return sources
    .map((s) => {
      if (typeof s === 'string') {
        // Could be a URL or plain name
        if (s.startsWith('http')) {
          const domain = domainFromUrl(s);
          return `<a href="${esc(s)}" target="_blank" rel="noopener" class="source-link">${domain}</a>`;
        }
        return `<span class="source-name">${esc(s)}</span>`;
      }
      // Object with name/url
      const name = s.name || s.source || domainFromUrl(s.url || '');
      const url = s.url || s.link || '';
      if (url) {
        return `<a href="${esc(url)}" target="_blank" rel="noopener" class="source-link">${esc(name)}</a>`;
      }
      return `<span class="source-name">${esc(name)}</span>`;
    })
    .join(' ');
}

function domainFromUrl(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}
