/**
 * export.js — Download functions for clean and redline documents.
 * Supports individual file downloads and zipped bundles.
 */

/* global JSZip */

import { getDocument, getAllDocuments, getAllReplacements } from './storage.js';
import { applyDocxCleanReplacements, applyDocxRedlineReplacements } from './docx-processor.js';
import { applyPdfCleanReplacements, applyPdfRedlineReplacements } from './pdf-processor.js';

/**
 * Gathers active replacements grouped by document id.
 * @returns {Promise<Map<number, Array>>} Map of docId -> array of active replacement configs.
 */
async function getActiveReplacementsByDoc() {
  const allReplacements = await getAllReplacements();
  const byDoc = new Map();

  for (const r of allReplacements) {
    if (!r.active) continue;
    if (!r.replace && r.replace !== '') continue;

    if (!byDoc.has(r.docId)) {
      byDoc.set(r.docId, []);
    }
    byDoc.get(r.docId).push({
      find: r.find,
      replace: r.replace,
      isBracket: r.source === 'auto'
    });
  }

  return byDoc;
}

/**
 * Triggers a browser download of the given data.
 * @param {ArrayBuffer|Uint8Array} data - The file data.
 * @param {string} filename - The download filename.
 * @param {string} mimeType - The MIME type.
 */
function downloadFile(data, filename, mimeType) {
  const blob = new Blob([data], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Gets the MIME type for a document based on its type string.
 * @param {string} type - 'docx' or 'pdf'.
 * @returns {string} The MIME type string.
 */
function getMimeType(type) {
  if (type === 'docx') {
    return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  }
  return 'application/pdf';
}

/**
 * Generates a clean filename with a suffix before the extension.
 * @param {string} name - Original filename.
 * @param {string} suffix - Suffix to add (e.g., '-clean', '-redline').
 * @returns {string} Modified filename.
 */
function addSuffix(name, suffix) {
  const dotIndex = name.lastIndexOf('.');
  if (dotIndex === -1) return name + suffix;
  return name.substring(0, dotIndex) + suffix + name.substring(dotIndex);
}

/**
 * Processes a single document with clean replacements.
 * @param {Object} doc - Document record from IndexedDB.
 * @param {Array} replacements - Array of replacement configs for this doc.
 * @returns {Promise<ArrayBuffer>} The processed document data.
 */
async function processClean(doc, replacements) {
  if (!replacements || replacements.length === 0) {
    return doc.data;
  }
  if (doc.type === 'docx') {
    return applyDocxCleanReplacements(doc.data, replacements);
  } else {
    return applyPdfCleanReplacements(doc.data, replacements);
  }
}

/**
 * Processes a single document with redline replacements.
 * @param {Object} doc - Document record from IndexedDB.
 * @param {Array} replacements - Array of replacement configs for this doc.
 * @returns {Promise<ArrayBuffer>} The processed document data.
 */
async function processRedline(doc, replacements) {
  if (!replacements || replacements.length === 0) {
    return doc.data;
  }
  if (doc.type === 'docx') {
    return applyDocxRedlineReplacements(doc.data, replacements);
  } else {
    return applyPdfRedlineReplacements(doc.data, replacements);
  }
}

/**
 * Downloads each document individually with clean replacements applied.
 * @param {Function} onProgress - Callback with progress text updates.
 * @returns {Promise<number>} Number of documents exported.
 */
export async function exportCleanIndividual(onProgress) {
  const byDoc = await getActiveReplacementsByDoc();
  const docs = await getAllDocuments();

  if (docs.length === 0) {
    throw new Error('No documents to export.');
  }

  let count = 0;
  for (const doc of docs) {
    onProgress(`Processing ${doc.name} (${count + 1}/${docs.length})...`);
    const replacements = byDoc.get(doc.id) || [];
    const result = await processClean(doc, replacements);
    const filename = addSuffix(doc.name, '-clean');
    downloadFile(result, filename, getMimeType(doc.type));
    count++;
  }

  return count;
}

/**
 * Downloads all documents in a zip with clean replacements applied.
 * @param {Function} onProgress - Callback with progress text updates.
 * @returns {Promise<number>} Number of documents included.
 */
export async function exportCleanZip(onProgress) {
  const byDoc = await getActiveReplacementsByDoc();
  const docs = await getAllDocuments();

  if (docs.length === 0) {
    throw new Error('No documents to export.');
  }

  const zip = new JSZip();
  let count = 0;

  for (const doc of docs) {
    onProgress(`Processing ${doc.name} (${count + 1}/${docs.length})...`);
    const replacements = byDoc.get(doc.id) || [];
    const result = await processClean(doc, replacements);
    const filename = addSuffix(doc.name, '-clean');
    zip.file(filename, result);
    count++;
  }

  onProgress('Creating zip file...');
  const zipData = await zip.generateAsync({ type: 'arraybuffer' });
  downloadFile(zipData, 'clean-documents.zip', 'application/zip');

  return count;
}

/**
 * Downloads each document individually with redline markup.
 * @param {Function} onProgress - Callback with progress text updates.
 * @returns {Promise<number>} Number of documents exported.
 */
export async function exportRedlineIndividual(onProgress) {
  const byDoc = await getActiveReplacementsByDoc();
  const docs = await getAllDocuments();

  if (docs.length === 0) {
    throw new Error('No documents to export.');
  }

  let count = 0;
  for (const doc of docs) {
    onProgress(`Processing ${doc.name} (${count + 1}/${docs.length})...`);
    const replacements = byDoc.get(doc.id) || [];
    const result = await processRedline(doc, replacements);
    const filename = addSuffix(doc.name, '-redline');
    downloadFile(result, filename, getMimeType(doc.type));
    count++;
  }

  return count;
}

/**
 * Downloads all documents in a zip with redline markup.
 * @param {Function} onProgress - Callback with progress text updates.
 * @returns {Promise<number>} Number of documents included.
 */
export async function exportRedlineZip(onProgress) {
  const byDoc = await getActiveReplacementsByDoc();
  const docs = await getAllDocuments();

  if (docs.length === 0) {
    throw new Error('No documents to export.');
  }

  const zip = new JSZip();
  let count = 0;

  for (const doc of docs) {
    onProgress(`Processing ${doc.name} (${count + 1}/${docs.length})...`);
    const replacements = byDoc.get(doc.id) || [];
    const result = await processRedline(doc, replacements);
    const filename = addSuffix(doc.name, '-redline');
    zip.file(filename, result);
    count++;
  }

  onProgress('Creating zip file...');
  const zipData = await zip.generateAsync({ type: 'arraybuffer' });
  downloadFile(zipData, 'redline-documents.zip', 'application/zip');

  return count;
}
