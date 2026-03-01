/**
 * weekly-snapshot.js
 * Renders the Weekly Snapshot section: top stories, one-to-watch, and quick stats.
 */

import { SENTIMENT_COLORS, formatCurrency, formatNumber } from './chart-utils.js';

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

/**
 * @param {HTMLElement} container — the section element to render into
 * @param {Object}      data     — full dashboard data (uses data.latest)
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

  let html = '<h2 class="section-title">Weekly Snapshot</h2>';

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
  html += quickStatsRow(stats, digest);

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

function quickStatsRow(stats, digest) {
  const totalArticles   = stats.total_articles_analyzed ?? stats.total_articles ?? stats.article_count ?? 0;
  const fundingTotal    = stats.funding_total_usd ?? stats.funding_total ?? stats.total_funding ?? 0;
  const regulationCount = stats.new_regulations_count ?? stats.regulations_count ?? stats.regulation_count ?? 0;
  const launches        = stats.product_launches_count ?? stats.product_launches ?? stats.launch_count ?? 0;
  const dominantTopic   = stats.dominant_topic ?? stats.top_topic ?? '';
  const sentimentDist   = stats.sentiment_balance ?? stats.sentiment_distribution ?? stats.sentiment ?? null;

  let html = '<div class="quick-stats">';

  html += statCard('Articles', formatNumber(totalArticles), 'article-count');
  html += statCard('Funding', formatCurrency(fundingTotal), 'funding-total');
  html += statCard('Regulations', formatNumber(regulationCount), 'regulation-count');
  html += statCard('Launches', formatNumber(launches), 'launch-count');

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

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

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
