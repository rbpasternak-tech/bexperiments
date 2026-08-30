export function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function detectCase(str) {
  if (str === str.toUpperCase() && str !== str.toLowerCase()) return 'upper';
  if (str === str.toLowerCase()) return 'lower';
  const words = str.split(/\s+/);
  if (words.length > 1 && words.every((w) => /^[A-Z]/.test(w))) return 'title';
  if (/^[A-Z]/.test(str) && str.slice(1) === str.slice(1).toLowerCase()) return 'capitalized';
  return 'mixed';
}

export function applyCase(replacement, caseType) {
  switch (caseType) {
    case 'upper': return replacement.toUpperCase();
    case 'lower': return replacement.toLowerCase();
    case 'title':
      return replacement.split(/\s+/).map(
        (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()
      ).join(' ');
    case 'capitalized':
      return replacement.charAt(0).toUpperCase() + replacement.slice(1);
    default: return replacement;
  }
}

export function applyReplacement(text, find, replace, isBracket) {
  if (!text || !find) {
    return { newText: text || '', count: 0, positions: [] };
  }

  const escaped = escapeRegex(find);
  let patternStr;
  if (isBracket) {
    patternStr = '\\[' + escaped + '\\](?:[\'\\u2019]s)?';
  } else {
    patternStr = '\\b' + escaped + '(?:[\'\\u2019]s)?\\b';
  }
  const pattern = new RegExp(patternStr, 'gi');

  const positions = [];
  let match;
  while ((match = pattern.exec(text)) !== null) {
    positions.push({
      start: match.index,
      end: match.index + match[0].length,
      original: match[0]
    });
  }

  const newText = text.replace(pattern, (matched) => {
    const hasPossessive = /['’]s$/i.test(matched);
    const core = hasPossessive ? matched.slice(0, -2) : matched;
    const inner = isBracket ? core.slice(1, -1) : core;
    const caseType = detectCase(inner);
    let result = applyCase(replace, caseType);
    if (hasPossessive) {
      result += result.endsWith('s') || result.endsWith('S') ? "'" : "'s";
    }
    return result;
  });

  return { newText, count: positions.length, positions };
}

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
