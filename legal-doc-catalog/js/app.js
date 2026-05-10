import { supabase } from './supabase-client.js';
import { renderAuth, renderHeaderUser } from './auth.js';
import { renderCatalog, renderSearchResults, renderDetail, renderLoading } from './views.js';
import { fetchAllDocuments, fetchDocument, searchDocuments, debounceSearch } from './search.js';

const authContainer = document.getElementById('auth-container');
const appContent = document.getElementById('app-content');
const headerActions = document.getElementById('header-actions');
const toastContainer = document.getElementById('toast-container');

let allDocuments = [];
let categories = [];
let years = [];
let filters = { category: '', year: '', query: '' };

function showToast(message, type = 'info', duration = 4000) {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

function extractFilters(docs) {
  const cats = [...new Set(docs.map(d => d.category))].sort();
  const yrs = [...new Set(docs.map(d => d.year))].sort((a, b) => {
    if (a === null) return 1;
    if (b === null) return -1;
    return a - b;
  });
  return { cats, yrs };
}

function applyFilters(docs) {
  return docs.filter(d => {
    if (filters.category && d.category !== filters.category) return false;
    if (filters.year === 'undated' && d.year !== null) return false;
    if (filters.year && filters.year !== 'undated' && d.year !== Number(filters.year)) return false;
    return true;
  });
}

async function loadCatalog() {
  renderLoading(appContent);
  try {
    allDocuments = await fetchAllDocuments();
    const { cats, yrs } = extractFilters(allDocuments);
    categories = cats;
    years = yrs;
    renderFilteredCatalog();
  } catch (err) {
    showToast('Failed to load documents: ' + err.message, 'error');
  }
}

function renderFilteredCatalog() {
  const filtered = applyFilters(allDocuments);
  renderCatalog(appContent, filtered, categories, years, filters, {
    onFilterCategory(val) {
      filters.category = val;
      renderFilteredCatalog();
    },
    onFilterYear(val) {
      filters.year = val;
      renderFilteredCatalog();
    },
    onSearch(query) {
      filters.query = query;
      if (!query) {
        renderFilteredCatalog();
        return;
      }
      debounceSearch(query, async (q) => {
        window.location.hash = `/search?q=${encodeURIComponent(q)}`;
      });
    }
  });
}

async function loadSearchResults(query) {
  renderLoading(appContent);
  try {
    const results = await searchDocuments(query);
    renderSearchResults(appContent, results, query);
    const searchInput = appContent.querySelector('#search-input');
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        const val = searchInput.value.trim();
        if (!val) {
          window.location.hash = '/';
          return;
        }
        debounceSearch(val, (q) => {
          window.location.hash = `/search?q=${encodeURIComponent(q)}`;
        });
      });
    }
  } catch (err) {
    showToast('Search failed: ' + err.message, 'error');
  }
}

async function loadDetail(id) {
  renderLoading(appContent);
  try {
    const doc = await fetchDocument(id);
    renderDetail(appContent, doc);
  } catch (err) {
    showToast('Failed to load document: ' + err.message, 'error');
    window.location.hash = '/';
  }
}

function route() {
  const hash = window.location.hash || '#/';

  const docMatch = hash.match(/^#\/doc\/(.+)$/);
  if (docMatch) {
    loadDetail(docMatch[1]);
    return;
  }

  const searchMatch = hash.match(/^#\/search\?q=(.+)$/);
  if (searchMatch) {
    loadSearchResults(decodeURIComponent(searchMatch[1]));
    return;
  }

  loadCatalog();
}

function showApp(session) {
  authContainer.hidden = true;
  appContent.hidden = false;
  renderHeaderUser(headerActions, session);
  route();
}

function showAuth() {
  authContainer.hidden = false;
  appContent.hidden = true;
  headerActions.innerHTML = '';
  renderAuth(authContainer, () => {});
}

async function init() {
  const { data: { session } } = await supabase.auth.getSession();
  if (session) {
    showApp(session);
  } else {
    showAuth();
  }

  supabase.auth.onAuthStateChange((_event, session) => {
    if (session) {
      showApp(session);
    } else {
      showAuth();
    }
  });

  window.addEventListener('hashchange', () => {
    const { data } = supabase.auth.getSession();
    if (authContainer.hidden) route();
  });
}

init();
