/**
 * docx-processor.js — Read/write .docx files via JSZip + XML DOM manipulation.
 * Handles text extraction, clean replacement, and redline (tracked changes) generation.
 */

import { escapeRegex } from './replacer.js';

/**
 * Reads a .docx ArrayBuffer and extracts all text content.
 * Concatenates text from all paragraphs in word/document.xml.
 * @param {ArrayBuffer} data - The .docx file as an ArrayBuffer.
 * @returns {Promise<string>} The extracted plain text.
 */
export async function readDocxText(data) {
  const zip = await JSZip.loadAsync(data);
  const xmlStr = await zip.file('word/document.xml').async('string');
  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(xmlStr, 'application/xml');

  const paragraphs = xmlDoc.getElementsByTagName('w:p');
  const textParts = [];

  for (let i = 0; i < paragraphs.length; i++) {
    const runs = paragraphs[i].getElementsByTagName('w:t');
    let paraText = '';
    for (let j = 0; j < runs.length; j++) {
      paraText += runs[j].textContent || '';
    }
    textParts.push(paraText);
  }

  return textParts.join('\n');
}

/**
 * Applies clean replacements to a .docx file and returns the modified ArrayBuffer.
 * For each paragraph, concatenates text, applies replacements, and writes back
 * into the first w:t element, clearing subsequent w:t elements.
 * @param {ArrayBuffer} data - Original .docx ArrayBuffer.
 * @param {Array<{find: string, replace: string, isBracket: boolean}>} replacements - Replacement operations.
 * @returns {Promise<ArrayBuffer>} The modified .docx as ArrayBuffer.
 */
export async function applyDocxCleanReplacements(data, replacements) {
  const zip = await JSZip.loadAsync(data);
  const xmlStr = await zip.file('word/document.xml').async('string');
  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(xmlStr, 'application/xml');

  const paragraphs = xmlDoc.getElementsByTagName('w:p');

  for (let i = 0; i < paragraphs.length; i++) {
    const wts = paragraphs[i].getElementsByTagName('w:t');
    if (wts.length === 0) continue;

    let paraText = '';
    for (let j = 0; j < wts.length; j++) {
      paraText += wts[j].textContent || '';
    }

    let modified = paraText;
    for (const r of replacements) {
      if (r.replace === undefined || r.replace === null) continue;
      let pattern;
      if (r.isBracket) {
        pattern = new RegExp('\\[' + escapeRegex(r.find) + '\\]', 'gi');
      } else {
        pattern = new RegExp('\\b' + escapeRegex(r.find) + '\\b', 'gi');
      }
      modified = modified.replace(pattern, r.replace);
    }

    if (modified !== paraText) {
      wts[0].textContent = modified;
      wts[0].setAttribute('xml:space', 'preserve');
      for (let j = wts.length - 1; j >= 1; j--) {
        wts[j].textContent = '';
      }
    }
  }

  const serializer = new XMLSerializer();
  const newXml = serializer.serializeToString(xmlDoc);
  zip.file('word/document.xml', newXml);

  return zip.generateAsync({ type: 'arraybuffer' });
}

/**
 * Creates a .docx with tracked changes (redlines) for the given replacements.
 * Uses w:del and w:ins XML elements to mark deletions and insertions.
 * @param {ArrayBuffer} data - Original .docx ArrayBuffer.
 * @param {Array<{find: string, replace: string, isBracket: boolean}>} replacements - Replacement operations.
 * @returns {Promise<ArrayBuffer>} The redlined .docx as ArrayBuffer.
 */
export async function applyDocxRedlineReplacements(data, replacements) {
  const zip = await JSZip.loadAsync(data);
  const xmlStr = await zip.file('word/document.xml').async('string');
  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(xmlStr, 'application/xml');

  const nsUri = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
  let changeId = 100;
  const dateStr = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  const author = 'Find & Replace Tool';

  const paragraphs = xmlDoc.getElementsByTagName('w:p');

  for (let pi = 0; pi < paragraphs.length; pi++) {
    const para = paragraphs[pi];
    const runs = Array.from(para.getElementsByTagName('w:r'));
    if (runs.length === 0) continue;

    // Collect run info: text and rPr (run properties) for each run
    const runInfos = runs.map((run) => {
      const wts = run.getElementsByTagName('w:t');
      let text = '';
      for (let j = 0; j < wts.length; j++) {
        text += wts[j].textContent || '';
      }
      const rPr = run.getElementsByTagName('w:rPr')[0] || null;
      return { run, text, rPr: rPr ? rPr.cloneNode(true) : null };
    });

    const fullText = runInfos.map((ri) => ri.text).join('');

    // Find all matches across all replacements in this paragraph
    const allMatches = [];
    for (const r of replacements) {
      if (r.replace === undefined || r.replace === null) continue;
      let pattern;
      if (r.isBracket) {
        pattern = new RegExp('\\[' + escapeRegex(r.find) + '\\]', 'gi');
      } else {
        pattern = new RegExp('\\b' + escapeRegex(r.find) + '\\b', 'gi');
      }
      let m;
      while ((m = pattern.exec(fullText)) !== null) {
        allMatches.push({
          start: m.index,
          end: m.index + m[0].length,
          original: m[0],
          replacement: r.replace
        });
      }
    }

    if (allMatches.length === 0) continue;

    // Sort matches by start position; non-overlapping assumed
    allMatches.sort((a, b) => a.start - b.start);

    // Build new paragraph children
    // Remove all w:r elements from paragraph
    for (const ri of runInfos) {
      if (ri.run.parentNode === para) {
        para.removeChild(ri.run);
      }
    }

    // Get the rPr from first run as a default
    const defaultRPr = runInfos.length > 0 ? runInfos[0].rPr : null;

    // Build segments: text before/between/after matches, plus del/ins for each match
    let cursor = 0;
    for (const match of allMatches) {
      // Text before this match
      if (cursor < match.start) {
        const beforeText = fullText.substring(cursor, match.start);
        const runEl = createRun(xmlDoc, nsUri, beforeText, defaultRPr);
        para.appendChild(runEl);
      }

      // w:del element
      const delEl = xmlDoc.createElementNS(nsUri, 'w:del');
      delEl.setAttribute('w:id', String(changeId++));
      delEl.setAttribute('w:author', author);
      delEl.setAttribute('w:date', dateStr);
      const delRun = xmlDoc.createElementNS(nsUri, 'w:r');
      delRun.setAttribute('w:rsidDel', '00000001');
      if (defaultRPr) {
        delRun.appendChild(defaultRPr.cloneNode(true));
      }
      const delText = xmlDoc.createElementNS(nsUri, 'w:delText');
      delText.setAttribute('xml:space', 'preserve');
      delText.textContent = match.original;
      delRun.appendChild(delText);
      delEl.appendChild(delRun);
      para.appendChild(delEl);

      // w:ins element
      const insEl = xmlDoc.createElementNS(nsUri, 'w:ins');
      insEl.setAttribute('w:id', String(changeId++));
      insEl.setAttribute('w:author', author);
      insEl.setAttribute('w:date', dateStr);
      const insRun = xmlDoc.createElementNS(nsUri, 'w:r');
      insRun.setAttribute('w:rsidR', '00000001');
      if (defaultRPr) {
        insRun.appendChild(defaultRPr.cloneNode(true));
      }
      const insText = xmlDoc.createElementNS(nsUri, 'w:t');
      insText.setAttribute('xml:space', 'preserve');
      insText.textContent = match.replacement;
      insRun.appendChild(insText);
      insEl.appendChild(insRun);
      para.appendChild(insEl);

      cursor = match.end;
    }

    // Text after last match
    if (cursor < fullText.length) {
      const afterText = fullText.substring(cursor);
      const runEl = createRun(xmlDoc, nsUri, afterText, defaultRPr);
      para.appendChild(runEl);
    }
  }

  const serializer = new XMLSerializer();
  const newXml = serializer.serializeToString(xmlDoc);
  zip.file('word/document.xml', newXml);

  return zip.generateAsync({ type: 'arraybuffer' });
}

/**
 * Helper: creates a w:r element with text and optional run properties.
 * @param {Document} xmlDoc - The XML document.
 * @param {string} nsUri - Namespace URI for w: elements.
 * @param {string} text - Text content.
 * @param {Element|null} rPr - Run properties element to clone, or null.
 * @returns {Element} The w:r element.
 */
function createRun(xmlDoc, nsUri, text, rPr) {
  const run = xmlDoc.createElementNS(nsUri, 'w:r');
  if (rPr) {
    run.appendChild(rPr.cloneNode(true));
  }
  const wt = xmlDoc.createElementNS(nsUri, 'w:t');
  wt.setAttribute('xml:space', 'preserve');
  wt.textContent = text;
  run.appendChild(wt);
  return run;
}
