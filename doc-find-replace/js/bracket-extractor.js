/**
 * bracket-extractor.js — Extract [bracketed] words from document text.
 * Returns unique bracketed terms found in a given text string.
 */

/**
 * Extracts unique [word] patterns from text.
 * Words inside brackets may contain letters, numbers, spaces, and hyphens.
 * Returns deduplicated list within the given text.
 * @param {string} text - The text to search for bracketed terms.
 * @returns {Array<{find: string, findRaw: string}>} Array of extracted terms.
 */
export function extractBracketedTerms(text) {
  if (!text || typeof text !== 'string') {
    return [];
  }

  const regex = /\[([a-zA-Z0-9][a-zA-Z0-9 -]*[a-zA-Z0-9])\]/g;
  const singleCharRegex = /\[([a-zA-Z0-9])\]/g;
  const seen = new Set();
  const results = [];
  let match;

  while ((match = regex.exec(text)) !== null) {
    const word = match[1];
    const key = word.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      results.push({
        find: word,
        findRaw: match[0]
      });
    }
  }

  while ((match = singleCharRegex.exec(text)) !== null) {
    const word = match[1];
    const key = word.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      results.push({
        find: word,
        findRaw: match[0]
      });
    }
  }

  return results;
}
