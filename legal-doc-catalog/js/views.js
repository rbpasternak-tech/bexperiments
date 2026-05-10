import { escapeHtml, escapeAttr, humanizeCategory, sanitizeHeadline } from './util.js';

export function renderCatalog(container, documents, categories, years, filters, handlers) {
  const categoryOptions = categories
    .map(c => `<option value="${escapeAttr(c)}"${filters.category === c ? ' selected' : ''}>${escapeHtml(humanizeCategory(c))}</option>`)
    .join('');
  const yearOptions = years
    .map(y => {
      const label = y === null ? 'Undated' : y;
      const val = y === null ? 'undated' : y;
      return `<option value="${escapeAttr(String(val))}"${String(filters.year) === String(val) ? ' selected' : ''}>${label}</option>`;
    })
    .join('');

  const totalShown = documents.length;

  container.innerHTML = `
    <div class="catalog-toolbar">
      <div class="catalog-stats">${totalShown} document${totalShown !== 1 ? 's' : ''}</div>
      <div class="catalog-filters">
        <select id="filter-category">
          <option value="">All Categories</option>
          ${categoryOptions}
        </select>
        <select id="filter-year">
          <option value="">All Years</option>
          ${yearOptions}
        </select>
      </div>
      <div class="search-bar">
        <input type="search" id="search-input" placeholder="Search documents..." value="${escapeAttr(filters.query || '')}">
      </div>
    </div>
    <div class="card-grid" id="card-grid">
      ${documents.length === 0
        ? '<p class="empty-state">No documents match your filters.</p>'
        : documents.map(doc => renderCard(doc)).join('')}
    </div>
  `;

  container.querySelector('#filter-category').addEventListener('change', (e) => {
    handlers.onFilterCategory(e.target.value);
  });
  container.querySelector('#filter-year').addEventListener('change', (e) => {
    handlers.onFilterYear(e.target.value);
  });
  const searchInput = container.querySelector('#search-input');
  searchInput.addEventListener('input', () => {
    handlers.onSearch(searchInput.value.trim());
  });
}

function renderCard(doc) {
  const category = humanizeCategory(doc.category);
  const yearLabel = doc.year || 'Undated';
  return `
    <a class="doc-card" href="#/doc/${doc.id}">
      <div class="doc-card-title">${escapeHtml(doc.title)}</div>
      <div class="doc-card-meta">
        <span class="badge badge-category">${escapeHtml(category)}</span>
        <span class="badge badge-year">${escapeHtml(String(yearLabel))}</span>
      </div>
      <div class="doc-card-words">${doc.word_count.toLocaleString()} words</div>
    </a>
  `;
}

export function renderSearchResults(container, results, query) {
  container.innerHTML = `
    <div class="catalog-toolbar">
      <div class="catalog-stats">${results.length} result${results.length !== 1 ? 's' : ''} for "${escapeHtml(query)}"</div>
      <div class="search-bar">
        <input type="search" id="search-input" placeholder="Search documents..." value="${escapeAttr(query)}">
      </div>
      <a href="#/" class="btn-back">Back to catalog</a>
    </div>
    <div class="search-results">
      ${results.length === 0
        ? '<p class="empty-state">No results found.</p>'
        : results.map(r => renderSearchResult(r)).join('')}
    </div>
  `;
}

function renderSearchResult(result) {
  const category = humanizeCategory(result.category);
  const yearLabel = result.year || 'Undated';
  return `
    <a class="search-result" href="#/doc/${result.id}">
      <div class="search-result-title">${escapeHtml(result.title)}</div>
      <div class="doc-card-meta">
        <span class="badge badge-category">${escapeHtml(category)}</span>
        <span class="badge badge-year">${escapeHtml(String(yearLabel))}</span>
      </div>
      <div class="search-result-snippet">${sanitizeHeadline(result.headline)}</div>
    </a>
  `;
}

export function renderDetail(container, doc) {
  const category = humanizeCategory(doc.category);
  const yearLabel = doc.year || 'Undated';
  const paragraphs = doc.body_text
    .split(/\n+/)
    .filter(p => p.trim())
    .map(p => `<p>${escapeHtml(p)}</p>`)
    .join('');

  container.innerHTML = `
    <div class="detail-header">
      <a href="#/" class="btn-back">Back to catalog</a>
    </div>
    <article class="detail-content">
      <h2 class="detail-title">${escapeHtml(doc.title)}</h2>
      <div class="detail-meta">
        <span class="badge badge-category">${escapeHtml(category)}</span>
        <span class="badge badge-year">${escapeHtml(String(yearLabel))}</span>
        <span class="detail-words">${doc.word_count.toLocaleString()} words</span>
        <span class="detail-filename">${escapeHtml(doc.filename)}</span>
      </div>
      <div class="detail-body">
        ${paragraphs || '<p class="empty-state">No text content available.</p>'}
      </div>
    </article>
  `;
}

export function renderLoading(container) {
  container.innerHTML = '<div class="loading">Loading...</div>';
}
