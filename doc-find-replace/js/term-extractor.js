import { escapeRegex } from './replacer.js';

const MINOR_WORDS = new Set([
  'of', 'the', 'and', 'or', 'for', 'in', 'on', 'to', 'by', 'a', 'an',
  'at', 'as', 'but', 'with', 'from', 'into', 'upon', 'per', 'under'
]);

const EXCLUDED_TERMS = new Set([
  'united states', 'new york', 'los angeles', 'san francisco',
  'district court', 'supreme court', 'court of appeals',
  'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
  'saturday', 'sunday', 'january', 'february', 'march', 'april',
  'june', 'july', 'august', 'september', 'october', 'november', 'december'
]);

export function extractBracketedTerms(text) {
  if (!text || typeof text !== 'string') return [];

  const regex = /\[([a-zA-Z0-9][a-zA-Z0-9 -]*[a-zA-Z0-9])\]/g;
  const singleCharRegex = /\[([a-zA-Z0-9])\]/g;
  const seen = new Set();
  const results = [];
  let match;

  while ((match = regex.exec(text)) !== null) {
    const key = match[1].toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      results.push({ find: match[1], findRaw: match[0], type: 'bracket' });
    }
  }

  while ((match = singleCharRegex.exec(text)) !== null) {
    const key = match[1].toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      results.push({ find: match[1], findRaw: match[0], type: 'bracket' });
    }
  }

  return results;
}

export function extractQuotedTerms(text) {
  if (!text || typeof text !== 'string') return [];

  const regex = /[\u0022\u201C\u201D]([^\u0022\u201C\u201D\n]{1,80})[\u0022\u201C\u201D]/g;
  const seen = new Set();
  const results = [];
  let match;

  while ((match = regex.exec(text)) !== null) {
    const term = match[1].trim();
    if (!term || term.length < 2) continue;
    if (!/^[A-Z]/.test(term)) continue;
    if (term.includes('.')) continue;

    const words = term.split(/\s+/);
    if (words.length > 8) continue;

    const sigCaps = words.filter(
      (w) => /^[A-Z]/.test(w) && !MINOR_WORDS.has(w.toLowerCase())
    );
    if (sigCaps.length === 0) continue;

    const key = term.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      results.push({ find: term, findRaw: match[0], type: 'quoted' });
    }
  }

  return results;
}

export function extractDefinedTerms(text) {
  if (!text || typeof text !== 'string') return [];

  const capWord = '[A-Z][a-z]+(?:-[A-Z][a-z]+)*';
  const minor = '(?:of|the|and|or|for|in|on|to|by|a|an|at|as|with|from)';
  const pattern = '\\b(' + capWord + '(?:\\s+' + minor + '\\s+' + capWord
    + '|\\s+' + capWord + ')+)\\b';
  const regex = new RegExp(pattern, 'g');
  const counts = new Map();
  let match;

  while ((match = regex.exec(text)) !== null) {
    let phrase = match[1];

    phrase = phrase.replace(/^(?:The|A|An)\s+/, '');

    const words = phrase.split(/\s+/);
    const sigWords = words.filter(
      (w) => /^[A-Z]/.test(w) && !MINOR_WORDS.has(w.toLowerCase())
    );
    if (sigWords.length < 2) continue;

    const key = phrase.toLowerCase();
    if (EXCLUDED_TERMS.has(key)) continue;

    const lineStart = text.lastIndexOf('\n', match.index - 1);
    const textBefore = text.substring(lineStart + 1, match.index).trim();
    if (textBefore === '') continue;

    if (counts.has(key)) {
      counts.get(key).count++;
    } else {
      counts.set(key, { original: phrase, count: 1 });
    }
  }

  const results = [];
  for (const [key, info] of counts) {
    if (info.count >= 2) {
      results.push({
        find: info.original,
        findRaw: info.original,
        type: 'defined'
      });
    }
  }

  return results;
}

export function extractAllTerms(text) {
  const bracketed = extractBracketedTerms(text);
  const quoted = extractQuotedTerms(text);
  const defined = extractDefinedTerms(text);

  const seen = new Set();
  const results = [];

  for (const term of [...bracketed, ...quoted, ...defined]) {
    const key = term.find.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      results.push(term);
    }
  }

  return results;
}

export function countTermOccurrences(text, find, source) {
  if (!text || !find) return 0;

  let pattern;
  if (source === 'bracket' || source === 'auto') {
    pattern = new RegExp('\\[' + escapeRegex(find) + '\\]', 'gi');
  } else {
    pattern = new RegExp('\\b' + escapeRegex(find) + '\\b', 'gi');
  }

  const matches = text.match(pattern);
  return matches ? matches.length : 0;
}
