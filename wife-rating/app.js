// The Wife Review — a (mostly) joke feedback app.
// Kevin rates wife performance across categories with a color-coded star
// scale, adds comments, and sends results back via link, email, or clipboard.
// No backend: results are base64-encoded into the URL hash.

// Optional: set this to prefill the "to" address on the email button.
const RECIPIENT_EMAIL = '';

const DRAFT_KEY = 'wife-review-draft';

const STAR_META = {
  1: { name: 'blue', label: 'Room to grow' },
  2: { name: 'green', label: 'Getting there' },
  3: { name: 'purple', label: 'Solid wife behavior' },
  4: { name: 'bronze', label: 'Excellent work' },
  5: { name: 'gold', label: 'World-class wife' },
};

const CATEGORIES = [
  { id: 'emotional', title: 'Emotional availability', desc: 'Present, tuned in, and emotionally online.' },
  { id: 'listening', title: 'Listening skills', desc: 'Actually hearing you — not just waiting to talk.' },
  { id: 'communication', title: 'Communication', desc: 'Says what she means. Means what she says.' },
  { id: 'thoughtfulness', title: 'Thoughtfulness', desc: 'The little things: snacks, notes, remembering stuff.' },
  { id: 'patience', title: 'Patience & grace', desc: 'Tolerance for your nonsense, measured in stars.' },
  { id: 'humor', title: 'Humor & fun', desc: 'Keeps married life entertaining.' },
  { id: 'support', title: 'Support & encouragement', desc: 'Number-one-fan energy when it counts.' },
  { id: 'affection', title: 'Affection', desc: 'Hugs, hand-holds, and general warmth.' },
  { id: 'overall', title: 'Overall wife rating', desc: 'The whole package. Think carefully.' },
];

const CHIPS = [
  'Made me laugh',
  'Gave great advice',
  'Best hugs',
  'Planned something fun',
  'Let me pick the show',
  'Brought me food',
  'Believed in me',
  'Put up with my nonsense',
  'Looked amazing',
  'Handled a hard thing like a champ',
];

const AGAIN_OPTIONS = ['Yes', 'Absolutely', 'In every universe'];

const state = {
  ratings: {},
  chips: [],
  again: null,
  keep: '',
  suggestion: '',
  comments: '',
};

export function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

export function escapeAttr(text) {
  return escapeHtml(text).replace(/"/g, '&quot;');
}

// --- Encoding: results object <-> URL hash ---

export function encodeResults(data) {
  const json = JSON.stringify(data);
  return btoa(String.fromCharCode(...new TextEncoder().encode(json)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function decodeResults(encoded) {
  try {
    const b64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
    const bytes = Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
}

function buildResultsData() {
  return {
    v: 1,
    date: new Date().toISOString(),
    ratings: state.ratings,
    chips: state.chips,
    again: state.again,
    keep: state.keep.trim(),
    suggestion: state.suggestion.trim(),
    comments: state.comments.trim(),
  };
}

function resultsUrl(data) {
  const base = `${location.origin}${location.pathname}`;
  return `${base}#r=${encodeResults(data)}`;
}

function averageRating(ratings) {
  const values = Object.values(ratings);
  if (!values.length) return 0;
  return values.reduce((sum, n) => sum + n, 0) / values.length;
}

// --- Rendering ---

function starRow(rating, { interactive, categoryId }) {
  const meta = STAR_META[rating];
  const colorClass = meta ? `stars-${meta.name}` : '';
  const stars = [1, 2, 3, 4, 5].map((n) => {
    const filled = rating >= n;
    const tag = interactive ? 'button' : 'span';
    const attrs = interactive
      ? ` type="button" data-cat="${escapeAttr(categoryId)}" data-value="${n}" aria-label="${n} star${n > 1 ? 's' : ''}"`
      : '';
    return `<${tag} class="star ${filled ? 'filled' : ''}"${attrs}>${filled ? '★' : '☆'}</${tag}>`;
  }).join('');
  const verdict = meta
    ? `<span class="star-verdict verdict-${meta.name}">${meta.label}</span>`
    : '<span class="star-verdict verdict-empty">Awaiting judgment&hellip;</span>';
  return `<div class="star-row ${colorClass}">${stars}${verdict}</div>`;
}

function renderLegend() {
  document.getElementById('legend-list').innerHTML = [1, 2, 3, 4, 5]
    .map((n) => {
      const meta = STAR_META[n];
      return `<li class="legend-item stars-${meta.name}">
        <span class="legend-stars">${'★'.repeat(n)}</span>
        <span class="legend-label">${meta.label}</span>
      </li>`;
    })
    .join('');
}

function renderCategories() {
  document.getElementById('categories').innerHTML = CATEGORIES
    .map((cat) => `<div class="category" data-cat-block="${escapeAttr(cat.id)}">
      <div class="category-text">
        <h3>${escapeHtml(cat.title)}</h3>
        <p>${escapeHtml(cat.desc)}</p>
      </div>
      ${starRow(state.ratings[cat.id] || 0, { interactive: true, categoryId: cat.id })}
    </div>`)
    .join('');
}

function renderChips() {
  document.getElementById('chips').innerHTML = CHIPS
    .map((chip) => `<button type="button" class="chip ${state.chips.includes(chip) ? 'selected' : ''}"
      data-chip="${escapeAttr(chip)}">${escapeHtml(chip)}</button>`)
    .join('');
}

function renderAgainOptions() {
  document.getElementById('again-options').innerHTML = AGAIN_OPTIONS
    .map((opt) => `<button type="button" class="again-option ${state.again === opt ? 'selected' : ''}"
      data-again="${escapeAttr(opt)}">${escapeHtml(opt)}</button>`)
    .join('');
}

function renderResults(data, { fromLink }) {
  document.getElementById('review-form').classList.add('hidden');
  const results = document.getElementById('results');
  results.classList.remove('hidden');

  const avg = averageRating(data.ratings);
  const rounded = Math.max(1, Math.min(5, Math.round(avg)));
  const meta = STAR_META[rounded];
  const dateStr = data.date
    ? new Date(data.date).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })
    : '';

  document.getElementById('results-title').textContent = fromLink
    ? 'A wife review has arrived'
    : 'Review submitted';

  document.getElementById('score-banner').innerHTML = `
    <div class="score-banner-inner stars-${meta.name}">
      <span class="score-stars">${'★'.repeat(rounded)}${'☆'.repeat(5 - rounded)}</span>
      <span class="score-number">${avg.toFixed(1)} / 5</span>
      <span class="score-verdict verdict-${meta.name}">${meta.label}</span>
      ${dateStr ? `<span class="score-date">Filed ${escapeHtml(dateStr)}</span>` : ''}
    </div>`;

  const categoryRows = CATEGORIES
    .filter((cat) => data.ratings[cat.id])
    .map((cat) => `<div class="category readonly">
      <div class="category-text"><h3>${escapeHtml(cat.title)}</h3></div>
      ${starRow(data.ratings[cat.id], { interactive: false })}
    </div>`)
    .join('');

  const chipsHtml = (data.chips || []).length
    ? `<h3 class="results-subhead">Highlights</h3>
       <div class="chips readonly">${data.chips.map((chip) => `<span class="chip selected">${escapeHtml(chip)}</span>`).join('')}</div>`
    : '';

  const writtenParts = [
    data.again && ['Would marry again?', data.again],
    data.keep && ['Keep doing', data.keep],
    data.suggestion && ['Gentle suggestion', data.suggestion],
    data.comments && ['Comments', data.comments],
  ].filter(Boolean);

  const writtenHtml = writtenParts.length
    ? `<h3 class="results-subhead">In their own words</h3>
       <dl class="written-feedback">${writtenParts
         .map(([label, value]) => `<div class="written-item"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`)
         .join('')}</dl>`
    : '';

  document.getElementById('results-body').innerHTML = categoryRows + chipsHtml + writtenHtml;

  // Recipients viewing a shared link don't need the send buttons.
  document.getElementById('send-card').classList.toggle('hidden', fromLink);
  document.getElementById('new-review-btn').textContent = fromLink
    ? 'Fill out your own review'
    : 'Start a fresh review';
}

// --- Summary text for email / clipboard ---

function buildSummaryText(data) {
  const lines = ['THE WIFE REVIEW — OFFICIAL RESULTS', ''];
  const avg = averageRating(data.ratings);
  lines.push(`Overall score: ${avg.toFixed(1)} / 5 (${STAR_META[Math.max(1, Math.round(avg))].label})`, '');
  CATEGORIES.forEach((cat) => {
    const rating = data.ratings[cat.id];
    if (rating) lines.push(`${cat.title}: ${'★'.repeat(rating)} (${rating}/5 — ${STAR_META[rating].label})`);
  });
  if ((data.chips || []).length) lines.push('', `Highlights: ${data.chips.join(', ')}`);
  if (data.again) lines.push('', `Would marry again? ${data.again}`);
  if (data.keep) lines.push(`Keep doing: ${data.keep}`);
  if (data.suggestion) lines.push(`Gentle suggestion: ${data.suggestion}`);
  if (data.comments) lines.push('', `Comments: ${data.comments}`);
  lines.push('', `Full results: ${resultsUrl(data)}`);
  return lines.join('\n');
}

async function copyToClipboard(text, statusMessage) {
  const status = document.getElementById('copy-status');
  try {
    await navigator.clipboard.writeText(text);
    status.textContent = statusMessage;
  } catch {
    status.textContent = 'Copy failed — you can copy the address bar URL instead.';
  }
  setTimeout(() => { status.textContent = ''; }, 4000);
}

// --- Draft persistence ---

function saveDraft() {
  localStorage.setItem(DRAFT_KEY, JSON.stringify(state));
}

function loadDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem(DRAFT_KEY));
    if (draft && typeof draft === 'object') Object.assign(state, draft);
  } catch {
    // Corrupt draft — start fresh.
  }
}

function clearDraft() {
  localStorage.removeItem(DRAFT_KEY);
}

// --- Form behavior ---

function updateSubmitHint() {
  const rated = Object.keys(state.ratings).length;
  const hint = document.getElementById('submit-hint');
  hint.textContent = rated < CATEGORIES.length
    ? `${rated} of ${CATEGORIES.length} categories rated`
    : 'All categories rated. The committee awaits.';
}

let formBound = false;

function bindFormEvents() {
  if (formBound) return;
  formBound = true;
  const form = document.getElementById('review-form');

  document.getElementById('categories').addEventListener('click', (event) => {
    const star = event.target.closest('.star[data-cat]');
    if (!star) return;
    const cat = star.dataset.cat;
    const value = Number(star.dataset.value);
    // Clicking the current rating clears it (change-of-heart support).
    if (state.ratings[cat] === value) delete state.ratings[cat];
    else state.ratings[cat] = value;
    renderCategories();
    updateSubmitHint();
    saveDraft();
  });

  document.getElementById('chips').addEventListener('click', (event) => {
    const chip = event.target.closest('.chip[data-chip]');
    if (!chip) return;
    const value = chip.dataset.chip;
    state.chips = state.chips.includes(value)
      ? state.chips.filter((item) => item !== value)
      : [...state.chips, value];
    renderChips();
    saveDraft();
  });

  document.getElementById('again-options').addEventListener('click', (event) => {
    const option = event.target.closest('.again-option[data-again]');
    if (!option) return;
    state.again = state.again === option.dataset.again ? null : option.dataset.again;
    renderAgainOptions();
    saveDraft();
  });

  [['keep-doing', 'keep'], ['suggestion', 'suggestion'], ['comments', 'comments']].forEach(([id, key]) => {
    const input = document.getElementById(id);
    input.value = state[key];
    input.addEventListener('input', () => {
      state[key] = input.value;
      saveDraft();
    });
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!Object.keys(state.ratings).length) {
      document.getElementById('submit-hint').textContent = 'Rate at least one category first — the stars are the whole point.';
      return;
    }
    const data = buildResultsData();
    history.replaceState(null, '', resultsUrl(data));
    clearDraft();
    renderResults(data, { fromLink: false });
    bindSendButtons(data);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

function bindSendButtons(data) {
  document.getElementById('copy-link-btn').onclick = () =>
    copyToClipboard(resultsUrl(data), 'Results link copied. Send it with confidence.');

  document.getElementById('copy-text-btn').onclick = () =>
    copyToClipboard(buildSummaryText(data), 'Summary copied to clipboard.');

  document.getElementById('email-btn').onclick = () => {
    const subject = encodeURIComponent('The Wife Review — Official Results');
    const body = encodeURIComponent(buildSummaryText(data));
    location.href = `mailto:${RECIPIENT_EMAIL}?subject=${subject}&body=${body}`;
  };
}

function startFreshReview() {
  history.replaceState(null, '', location.pathname);
  Object.assign(state, { ratings: {}, chips: [], again: null, keep: '', suggestion: '', comments: '' });
  clearDraft();
  document.getElementById('results').classList.add('hidden');
  const form = document.getElementById('review-form');
  form.classList.remove('hidden');
  bindFormEvents();
  renderCategories();
  renderChips();
  renderAgainOptions();
  [['keep-doing', 'keep'], ['suggestion', 'suggestion'], ['comments', 'comments']].forEach(([id, key]) => {
    document.getElementById(id).value = state[key];
  });
  updateSubmitHint();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- Init ---

function init() {
  renderLegend();
  document.getElementById('new-review-btn').addEventListener('click', startFreshReview);

  const match = location.hash.match(/^#r=(.+)$/);
  const shared = match && decodeResults(match[1]);
  if (shared && shared.ratings) {
    renderResults(shared, { fromLink: true });
    return;
  }

  loadDraft();
  document.getElementById('review-form').classList.remove('hidden');
  renderCategories();
  renderChips();
  renderAgainOptions();
  bindFormEvents();
  updateSubmitHint();
}

init();
