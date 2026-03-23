/**
 * replacer.js — Find/replace logic with whole-word, case-insensitive matching.
 * Supports both bracket-extracted terms and manual terms.
 */

/**
 * Escapes special regex characters in a string.
 * @param {string} str - The string to escape.
 * @returns {string} The escaped string safe for regex use.
 */
export function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Applies a single find/replace operation to text.
 * For bracket terms (isBracket=true): finds '[word]' literally (with brackets).
 * For manual terms: finds 'word' as whole word using word boundaries.
 * Matching is case-insensitive.
 *
 * @param {string} text - The input text.
 * @param {string} find - The term to find (without brackets for bracket terms).
 * @param {string} replace - The replacement text.
 * @param {boolean} isBracket - Whether this is a bracket-extracted term.
 * @returns {{newText: string, count: number, positions: Array<{start: number, end: number, original: string}>}}
 */
export function applyReplacement(text, find, replace, isBracket) {
  if (!text || !find) {
    return { newText: text || '', count: 0, positions: [] };
  }

  let pattern;
  if (isBracket) {
    pattern = new RegExp('\\[' + escapeRegex(find) + '\\]', 'gi');
  } else {
    pattern = new RegExp('\\b' + escapeRegex(find) + '\\b', 'gi');
  }

  const positions = [];
  let match;
  while ((match = pattern.exec(text)) !== null) {
    positions.push({
      start: match.index,
      end: match.index + match[0].length,
      original: match[0]
    });
  }

  const newText = text.replace(pattern, replace);
  return { newText, count: positions.length, positions };
}

/**
 * Applies multiple replacements to text in sequence.
 * @param {string} text - The input text.
 * @param {Array<{find: string, replace: string, isBracket: boolean}>} replacements - Replacement operations.
 * @returns {{newText: string, totalCount: number}}
 */
export function applyAllReplacements(text, replacements) {
  let currentText = text;
  let totalCount = 0;

  for (const r of replacements) {
    if (!r.replace && r.replace !== '') continue;
    const result = applyReplacement(currentText, r.find, r.replace, r.isBracket);
    currentText = result.newText;
    totalCount += result.count;
  }

  return { newText: currentText, totalCount };
}
