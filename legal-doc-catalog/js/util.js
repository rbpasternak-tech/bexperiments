export function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

export function escapeAttr(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function humanizeCategory(raw) {
  return raw
    .replace(/_and_/g, ' & ')
    .replace(/_/g, ' ');
}

export function formatTitle(filename) {
  let name = filename.replace(/\.docx$/i, '');
  name = name.replace(/_(\d{4})$/, '');
  return name.replace(/_/g, ' ');
}

export function parseYear(subfolder) {
  if (subfolder === 'undated') return null;
  const n = parseInt(subfolder, 10);
  return isNaN(n) ? null : n;
}

export function sanitizeHeadline(html) {
  const escaped = escapeHtml(html);
  return escaped
    .replace(/&lt;mark&gt;/g, '<mark>')
    .replace(/&lt;\/mark&gt;/g, '</mark>');
}
