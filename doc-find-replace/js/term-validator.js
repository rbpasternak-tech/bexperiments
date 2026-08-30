import { escapeRegex } from './replacer.js';

function countOccurrences(text, term, isBracket) {
  let patternStr;
  if (isBracket) {
    patternStr = '\\[' + escapeRegex(term) + '\\]';
  } else {
    patternStr = '\\b' + escapeRegex(term) + '\\b';
  }
  const matches = text.match(new RegExp(patternStr, 'gi'));
  return matches ? matches.length : 0;
}

export function validateTerms(text) {
  if (!text || typeof text !== 'string') {
    return { definedUnused: [], usedUndefined: [] };
  }

  const q = '[\\u0022\\u201C\\u201D]';
  const nq = '[^\\u0022\\u201C\\u201D\\n]';
  const definitionPatterns = [
    new RegExp(q + '([A-Z]' + nq + '{0,79})' + q + '\\s*(?:means|shall mean|refers to|has the meaning)', 'gi'),
    new RegExp('\\(\\s*(?:the\\s+)?' + q + '([A-Z]' + nq + '{0,79})' + q + '\\s*\\)', 'gi'),
    new RegExp('(?:hereinafter|herein)\\s+(?:referred to as|called)\\s+' + q + '([A-Z]' + nq + '{0,79})' + q, 'gi'),
    /\[([A-Z][a-zA-Z0-9 -]+)\]/g,
  ];

  const defined = new Map();
  for (const pattern of definitionPatterns) {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      const term = match[1].trim();
      if (term.length < 2) continue;
      const key = term.toLowerCase();
      const isBracket = match[0].startsWith('[');
      if (!defined.has(key)) {
        defined.set(key, { term, isBracket });
      }
    }
  }

  const definedUnused = [];
  for (const [key, info] of defined) {
    const total = countOccurrences(text, info.term, info.isBracket);
    const usagesOutsideDefinition = total - 1;
    if (usagesOutsideDefinition <= 0) {
      definedUnused.push({ term: info.term, usageCount: usagesOutsideDefinition });
    }
  }

  const capRegex = /\b([A-Z][a-z]+(?:-[A-Z][a-z]+)*(?:\s+(?:of|the|and|or|for|in|on|to|by|a|an|at|as|with|from)\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)*|\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)*)+)\b/g;
  const used = new Map();
  let match;
  while ((match = capRegex.exec(text)) !== null) {
    let term = match[1].trim();
    term = term.replace(/^(?:The|A|An)\s+/, '');
    if (term.length < 2) continue;
    const key = term.toLowerCase();
    if (!used.has(key)) {
      used.set(key, { term, count: 1 });
    } else {
      used.get(key).count++;
    }
  }

  const usedUndefined = [];
  for (const [key, info] of used) {
    if (info.count >= 3 && !defined.has(key)) {
      usedUndefined.push({ term: info.term, count: info.count });
    }
  }

  usedUndefined.sort((a, b) => b.count - a.count);
  definedUnused.sort((a, b) => a.term.localeCompare(b.term));

  return { definedUnused, usedUndefined };
}
