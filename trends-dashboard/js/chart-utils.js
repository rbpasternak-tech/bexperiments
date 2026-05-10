/**
 * chart-utils.js
 * Shared color palettes, Chart.js default configuration, and utility functions.
 */

/* ------------------------------------------------------------------ */
/*  Color Palettes                                                     */
/* ------------------------------------------------------------------ */

export const COLORS = {
  ai:             '#4F46E5', // indigo-600
  legal_tech:     '#7C3AED', // violet-600
  regulation:     '#DC2626', // red-600
  startup:        '#059669', // emerald-600
  enterprise:     '#2563EB', // blue-600
  open_source:    '#D97706', // amber-600
  security:       '#0891B2', // cyan-600
  data_privacy:   '#9333EA', // purple-600
  workforce:      '#EA580C', // orange-600
};

export const SENTIMENT_COLORS = {
  positive:     '#22C55E', // green-500
  neutral:      '#94A3B8', // slate-400
  negative:     '#EF4444', // red-500
  mixed:        '#F59E0B', // amber-500
  restrictive:  '#E11D48', // rose-600
  permissive:   '#10B981', // emerald-500
};

export const EVENT_COLORS = {
  funding:        '#6366F1', // indigo-500
  acquisition:    '#8B5CF6', // violet-500
  partnership:    '#3B82F6', // blue-500
  layoff:         '#EF4444', // red-500
  ipo:            '#14B8A6', // teal-500
  product_launch: '#22C55E', // green-500
};

/* ------------------------------------------------------------------ */
/*  Chart.js Global Defaults                                           */
/* ------------------------------------------------------------------ */

/**
 * Apply consistent Chart.js defaults. Call once at app start.
 * Assumes Chart is available globally via CDN.
 */
export function chartDefaults() {
  if (typeof Chart === 'undefined') {
    console.warn('Chart.js not loaded — skipping chartDefaults()');
    return;
  }

  Chart.defaults.font.family =
    "'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif";
  Chart.defaults.font.size = 13;
  Chart.defaults.color = '#334155';           // slate-700
  Chart.defaults.responsive = true;
  Chart.defaults.maintainAspectRatio = false;

  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.padding = 16;
  Chart.defaults.plugins.tooltip.backgroundColor = '#1E1B4B'; // indigo-950
  Chart.defaults.plugins.tooltip.cornerRadius = 6;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.titleFont = { weight: '600' };

  Chart.defaults.elements.line.tension = 0.3;
  Chart.defaults.elements.line.borderWidth = 2;
  Chart.defaults.elements.point.radius = 3;
  Chart.defaults.elements.point.hoverRadius = 5;

  Chart.defaults.scale.grid = {
    color: 'rgba(100, 116, 139, 0.12)',       // slate-500 @ 12%
  };
}

/* ------------------------------------------------------------------ */
/*  Utility: Heatmap Cell Color                                        */
/* ------------------------------------------------------------------ */

/**
 * Return an rgba() string on an indigo scale.
 * @param {number} value  — current cell value
 * @param {number} max    — maximum value in the dataset
 * @returns {string}        rgba color
 */
export function heatmapColor(value, max) {
  if (!max || max === 0) return 'rgba(79, 70, 229, 0.05)'; // near-transparent
  const ratio = Math.min(value / max, 1);
  // Indigo-600 base: rgb(79, 70, 229)
  const alpha = 0.08 + ratio * 0.82; // range 0.08 – 0.90
  return `rgba(79, 70, 229, ${alpha.toFixed(2)})`;
}

/* ------------------------------------------------------------------ */
/*  Utility: Number Formatting                                         */
/* ------------------------------------------------------------------ */

/**
 * Format large currency values in a compact way.
 *   2_400_000_000  ->  "$2.4B"
 *   750_000        ->  "$750K"
 *   1234           ->  "$1,234"
 */
export function formatCurrency(value) {
  if (value == null || isNaN(value)) return '$0';
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1e12)      return `${sign}$${(abs / 1e12).toFixed(1)}T`;
  if (abs >= 1e9)       return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6)       return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3)       return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${abs.toLocaleString()}`;
}

/**
 * Format a plain number with commas.
 */
export function formatNumber(value) {
  if (value == null || isNaN(value)) return '0';
  return Number(value).toLocaleString();
}

/**
 * Pick a color from the COLORS palette for a given key.
 * Falls back to a deterministic hash color when the key is unknown.
 */
export function colorForCategory(key) {
  if (COLORS[key]) return COLORS[key];
  // Simple hash to a palette-adjacent color
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = key.charCodeAt(i) + ((hash << 5) - hash);
  }
  const palette = Object.values(COLORS);
  return palette[Math.abs(hash) % palette.length];
}

/* ------------------------------------------------------------------ */
/*  Shared Helpers                                                     */
/* ------------------------------------------------------------------ */

/**
 * HTML-escape a string for safe DOM insertion.
 */
export function esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

/**
 * Format a date string as "Mon D" (e.g., "May 6").
 */
export function formatShortDate(dateStr) {
  try {
    const dateOnly = String(dateStr).slice(0, 10);
    const d = new Date(dateOnly + 'T00:00:00');
    if (isNaN(d)) return dateStr;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

/**
 * Capitalize first letter and replace underscores with spaces.
 */
export function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, ' ');
}

/**
 * Render a standard empty-state placeholder for a section.
 */
export function emptyState(title) {
  return `
    <h2 class="section-title">${title}</h2>
    <div class="empty-state">
      <p>No data yet</p>
    </div>`;
}
