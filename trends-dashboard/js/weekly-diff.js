/**
 * weekly-diff.js
 * Renders a "What Changed This Week" comparison between the two most recent digests.
 */

import { esc } from './chart-utils.js';

/**
 * @param {HTMLElement} container
 * @param {Object}      data — full dashboard data
 */
export function renderWeeklyDiff(container, data) {
  const digests = data.digests || [];
  if (digests.length < 2) {
    container.style.display = 'none';
    return;
  }
  container.style.display = '';

  const latest = digests[0];
  const previous = digests[1];

  const latestTopics = topicMap(latest);
  const prevTopics = topicMap(previous);

  const allNames = new Set([...latestTopics.keys(), ...prevTopics.keys()]);

  const rising = [];
  const falling = [];
  const brandNew = [];

  for (const name of allNames) {
    const cur = latestTopics.get(name) || 0;
    const prev = prevTopics.get(name) || 0;

    if (prev === 0 && cur > 0) {
      brandNew.push({ name, count: cur });
    } else if (cur > prev) {
      rising.push({ name, change: cur - prev, cur, prev });
    } else if (cur < prev) {
      falling.push({ name, change: prev - cur, cur, prev });
    }
  }

  rising.sort((a, b) => b.change - a.change);
  falling.sort((a, b) => b.change - a.change);

  let html = '<h2 class="section-title">What Changed This Week</h2>';
  html += '<div class="diff-grid">';

  // Rising column
  html += '<div class="diff-col">';
  html += '<h3>Rising Topics</h3>';
  if (rising.length === 0 && brandNew.length === 0) {
    html += '<p class="diff-empty">No rising topics</p>';
  } else {
    for (const t of brandNew.slice(0, 5)) {
      html += diffItem(t.name, 'NEW', 'new-topic');
    }
    for (const t of rising.slice(0, 5)) {
      html += diffItem(t.name, `+${t.change}`, 'up');
    }
  }
  html += '</div>';

  // Falling column
  html += '<div class="diff-col">';
  html += '<h3>Falling Topics</h3>';
  if (falling.length === 0) {
    html += '<p class="diff-empty">No falling topics</p>';
  } else {
    for (const t of falling.slice(0, 5)) {
      html += diffItem(t.name, `-${t.change}`, 'down');
    }
  }
  html += '</div>';

  html += '</div>';
  container.innerHTML = html;
}

function diffItem(name, label, cls) {
  return `
    <div class="diff-item">
      <span class="diff-topic">${esc(name)}</span>
      <span class="diff-change ${cls}">${label}</span>
    </div>`;
}

function topicMap(digest) {
  const map = new Map();
  for (const t of digest.topics || []) {
    const name = t.name || t.topic || 'Unknown';
    map.set(name, (map.get(name) || 0) + (t.mention_count ?? t.count ?? 1));
  }
  return map;
}
