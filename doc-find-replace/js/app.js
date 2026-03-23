/**
 * app.js — Main orchestrator for Doc Find & Replace.
 * Initializes UI, wires event handlers, manages document uploads,
 * bracket extraction, find/replace table, and export actions.
 */

import {
  openDb, addDocument, getAllDocuments, getDocument, deleteDocument,
  addReplacement, getAllReplacements, updateReplacement, deleteReplacement,
  deleteReplacementsByDocId
} from './storage.js';
import { readDocxText, applyDocxCleanReplacements } from './docx-processor.js';
import { readPdfText } from './pdf-processor.js';
import { extractBracketedTerms } from './bracket-extractor.js';
import { applyReplacement, applyAllReplacements } from './replacer.js';
import {
  exportCleanIndividual, exportCleanZip,
  exportRedlineIndividual, exportRedlineZip
} from './export.js';

// ─── DOM References ───

const docList = document.getElementById('doc-list');
const docStats = document.getElementById('doc-stats');
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');
const browseLink = document.getElementById('browse-link');
const replaceTbody = document.getElementById('replace-tbody');
const noRowsMsg = document.getElementById('no-rows-msg');
const tableFilter = document.getElementById('table-filter');
const checkAll = document.getElementById('check-all');
const btnAddRow = document.getElementById('btn-add-row');
const btnExtractAll = document.getElementById('btn-extract-all');
const btnApplyAll = document.getElementById('btn-apply-all');
const btnExportClean = document.getElementById('btn-export-clean');
const btnExportCleanZip = document.getElementById('btn-export-clean-zip');
const btnExportRedline = document.getElementById('btn-export-redline');
const btnExportRedlineZip = document.getElementById('btn-export-redline-zip');
const progressOverlay = document.getElementById('progress-overlay');
const progressText = document.getElementById('progress-text');
const toastContainer = document.getElementById('toast-container');

// ─── Helpers ───

/**
 * Escapes HTML special characters to prevent XSS when inserting into DOM.
 * @param {string} str - The string to escape.
 * @returns {string} Escaped HTML string.
 */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Formats byte size to human-readable string.
 * @param {number} bytes - Size in bytes.
 * @returns {string} Formatted size string.
 */
function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * Shows a toast notification.
 * @param {string} message - The message to display.
 * @param {string} type - 'success', 'error', 'warning', or 'info'.
 * @param {number} duration - Duration in ms before auto-dismiss.
 */
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

/**
 * Shows or hides the progress overlay.
 * @param {boolean} show - Whether to show.
 * @param {string} text - Progress message text.
 */
function setProgress(show, text = 'Processing...') {
  progressText.textContent = text;
  if (show) {
    progressOverlay.classList.remove('hidden');
  } else {
    progressOverlay.classList.add('hidden');
  }
}

/**
 * Gets the file extension type from a filename.
 * @param {string} name - Filename.
 * @returns {string} 'docx' or 'pdf'.
 */
function getFileType(name) {
  return name.toLowerCase().endsWith('.pdf') ? 'pdf' : 'docx';
}

// ─── Sidebar: Document List ───

/**
 * Refreshes the sidebar document list from IndexedDB.
 */
async function refreshDocList() {
  const docs = await getAllDocuments();
  docList.innerHTML = '';

  let totalSize = 0;
  for (const doc of docs) {
    totalSize += doc.size || 0;
    const li = document.createElement('li');
    li.innerHTML = `
      <span class="doc-name" title="${escapeHtml(doc.name)}">${escapeHtml(doc.name)}</span>
      <span class="doc-size">${formatSize(doc.size || 0)}</span>
      <button class="doc-delete" data-id="${doc.id}" title="Delete document">&times;</button>
    `;
    docList.appendChild(li);
  }

  docStats.textContent = docs.length > 0
    ? `${docs.length} doc${docs.length !== 1 ? 's' : ''} (${formatSize(totalSize)})`
    : '';

  // Wire delete buttons
  docList.querySelectorAll('.doc-delete').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      const id = Number(e.target.dataset.id);
      await deleteDocument(id);
      await deleteReplacementsByDocId(id);
      await refreshDocList();
      await refreshTable();
      showToast('Document removed.', 'info');
    });
  });
}

// ─── Upload Handling ───

/**
 * Processes uploaded files: stores in IndexedDB, extracts brackets, updates UI.
 * @param {FileList|Array<File>} files - The uploaded files.
 */
async function handleUpload(files) {
  const validFiles = Array.from(files).filter((f) => {
    const ext = f.name.toLowerCase();
    return ext.endsWith('.docx') || ext.endsWith('.pdf');
  });

  if (validFiles.length === 0) {
    showToast('No valid .docx or .pdf files selected.', 'warning');
    return;
  }

  setProgress(true, `Uploading ${validFiles.length} file(s)...`);

  try {
    let processed = 0;
    for (const file of validFiles) {
      processed++;
      setProgress(true, `Processing ${file.name} (${processed}/${validFiles.length})...`);

      const buffer = await file.arrayBuffer();
      const type = getFileType(file.name);

      const docId = await addDocument({
        name: file.name,
        type,
        data: buffer,
        size: file.size,
        dateAdded: new Date().toISOString()
      });

      // Extract brackets
      await extractAndStoreForDoc(docId, file.name, type, buffer);
    }

    await refreshDocList();
    await refreshTable();
    showToast(`Uploaded ${validFiles.length} file(s).`, 'success');
  } catch (err) {
    showToast('Upload error: ' + err.message, 'error');
    console.error(err);
  } finally {
    setProgress(false);
  }
}

/**
 * Extracts bracketed terms from a document and stores them as replacement records.
 * @param {number} docId - Document id.
 * @param {string} docName - Document filename.
 * @param {string} type - 'docx' or 'pdf'.
 * @param {ArrayBuffer} data - Document data.
 */
async function extractAndStoreForDoc(docId, docName, type, data) {
  let text;
  try {
    if (type === 'docx') {
      text = await readDocxText(data);
    } else {
      text = await readPdfText(data);
    }
  } catch (err) {
    console.error('Text extraction failed for', docName, err);
    return;
  }

  const terms = extractBracketedTerms(text);
  const existing = await getAllReplacements();
  const existingKeys = new Set(
    existing
      .filter((r) => r.docId === docId && r.source === 'auto')
      .map((r) => r.find.toLowerCase())
  );

  for (const term of terms) {
    if (!existingKeys.has(term.find.toLowerCase())) {
      await addReplacement({
        docId,
        docName,
        find: term.find,
        replace: '',
        source: 'auto',
        active: true
      });
    }
  }
}

// ─── Find/Replace Table ───

/**
 * Refreshes the find/replace table from IndexedDB.
 */
async function refreshTable() {
  const replacements = await getAllReplacements();
  replaceTbody.innerHTML = '';

  if (replacements.length === 0) {
    noRowsMsg.style.display = 'block';
    return;
  }

  noRowsMsg.style.display = 'none';

  for (const r of replacements) {
    const tr = document.createElement('tr');
    tr.dataset.id = r.id;
    tr.dataset.docId = r.docId;
    tr.dataset.source = r.source;
    tr.innerHTML = `
      <td title="${escapeHtml(r.docName)}">${escapeHtml(r.docName)}</td>
      <td><input type="text" value="${escapeHtml(r.find)}" data-field="find"></td>
      <td><input type="text" value="${escapeHtml(r.replace || '')}" data-field="replace" placeholder="Enter replacement..."></td>
      <td><span class="source-badge source-${r.source}">${r.source}</span></td>
      <td class="td-check"><input type="checkbox" ${r.active ? 'checked' : ''} data-field="active"></td>
      <td class="td-actions"><button class="row-delete" title="Delete row">&times;</button></td>
    `;
    replaceTbody.appendChild(tr);
  }

  wireTableEvents();
  applyFilter();
}

/**
 * Wires inline editing and row delete events to the table.
 */
function wireTableEvents() {
  // Inline editing for text inputs
  replaceTbody.querySelectorAll('input[type="text"]').forEach((input) => {
    input.addEventListener('change', async () => {
      const tr = input.closest('tr');
      const id = Number(tr.dataset.id);
      const field = input.dataset.field;
      const replacements = await getAllReplacements();
      const record = replacements.find((r) => r.id === id);
      if (record) {
        record[field] = input.value;
        await updateReplacement(record);
      }
    });
  });

  // Checkbox toggle
  replaceTbody.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
    cb.addEventListener('change', async () => {
      const tr = cb.closest('tr');
      const id = Number(tr.dataset.id);
      const replacements = await getAllReplacements();
      const record = replacements.find((r) => r.id === id);
      if (record) {
        record.active = cb.checked;
        await updateReplacement(record);
      }
    });
  });

  // Row delete
  replaceTbody.querySelectorAll('.row-delete').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const tr = btn.closest('tr');
      const id = Number(tr.dataset.id);
      await deleteReplacement(id);
      await refreshTable();
    });
  });
}

/**
 * Applies the filter input to show/hide table rows.
 */
function applyFilter() {
  const query = tableFilter.value.toLowerCase().trim();
  const rows = replaceTbody.querySelectorAll('tr');
  rows.forEach((tr) => {
    if (!query) {
      tr.classList.remove('hidden-row');
      return;
    }
    const text = tr.textContent.toLowerCase();
    if (text.includes(query)) {
      tr.classList.remove('hidden-row');
    } else {
      tr.classList.add('hidden-row');
    }
  });
}

// ─── Add Row ───

/**
 * Adds a manual find/replace row. Shows a simple prompt for document selection.
 */
async function handleAddRow() {
  const docs = await getAllDocuments();
  if (docs.length === 0) {
    showToast('Upload documents first before adding rows.', 'warning');
    return;
  }

  // Create a modal-like inline form
  const modal = document.createElement('div');
  modal.className = 'progress-overlay';
  modal.innerHTML = `
    <div class="progress-box" style="min-width: 350px;">
      <h3 style="margin-bottom: 16px; font-size: 16px;">Add Manual Row</h3>
      <div style="margin-bottom: 12px; text-align: left;">
        <label style="display: block; margin-bottom: 4px; font-size: 13px; color: #a0a0b8;">Document</label>
        <select id="add-row-doc" class="doc-select" style="width: 100%; padding: 8px; background: #252545; color: #f0f0f0; border: 1px solid #2a2a4a; border-radius: 6px;">
          <option value="all">All Documents</option>
          ${docs.map((d) => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('')}
        </select>
      </div>
      <div style="margin-bottom: 12px; text-align: left;">
        <label style="display: block; margin-bottom: 4px; font-size: 13px; color: #a0a0b8;">Find</label>
        <input type="text" id="add-row-find" style="width: 100%; padding: 8px; background: #252545; color: #f0f0f0; border: 1px solid #2a2a4a; border-radius: 6px;" placeholder="Text to find...">
      </div>
      <div style="margin-bottom: 16px; text-align: left;">
        <label style="display: block; margin-bottom: 4px; font-size: 13px; color: #a0a0b8;">Replace</label>
        <input type="text" id="add-row-replace" style="width: 100%; padding: 8px; background: #252545; color: #f0f0f0; border: 1px solid #2a2a4a; border-radius: 6px;" placeholder="Replacement text...">
      </div>
      <div style="display: flex; gap: 8px; justify-content: flex-end;">
        <button id="add-row-cancel" class="btn btn-secondary">Cancel</button>
        <button id="add-row-confirm" class="btn btn-action">Add</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  const findInput = modal.querySelector('#add-row-find');
  const replaceInput = modal.querySelector('#add-row-replace');
  const docSelect = modal.querySelector('#add-row-doc');

  findInput.focus();

  return new Promise((resolve) => {
    modal.querySelector('#add-row-cancel').addEventListener('click', () => {
      modal.remove();
      resolve();
    });

    modal.querySelector('#add-row-confirm').addEventListener('click', async () => {
      const findVal = findInput.value.trim();
      const replaceVal = replaceInput.value;
      const docVal = docSelect.value;

      if (!findVal) {
        showToast('Find text cannot be empty.', 'warning');
        return;
      }

      if (docVal === 'all') {
        for (const doc of docs) {
          await addReplacement({
            docId: doc.id,
            docName: doc.name,
            find: findVal,
            replace: replaceVal,
            source: 'manual',
            active: true
          });
        }
      } else {
        const doc = docs.find((d) => d.id === Number(docVal));
        if (doc) {
          await addReplacement({
            docId: doc.id,
            docName: doc.name,
            find: findVal,
            replace: replaceVal,
            source: 'manual',
            active: true
          });
        }
      }

      modal.remove();
      await refreshTable();
      showToast('Row added.', 'success');
      resolve();
    });

    // Allow Enter key in replace field to confirm
    replaceInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        modal.querySelector('#add-row-confirm').click();
      }
    });
    findInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        replaceInput.focus();
      }
    });
  });
}

// ─── Extract All Brackets ───

/**
 * Re-extracts bracketed terms from all stored documents.
 */
async function handleExtractAll() {
  const docs = await getAllDocuments();
  if (docs.length === 0) {
    showToast('No documents to extract from.', 'warning');
    return;
  }

  setProgress(true, 'Extracting bracketed terms...');

  try {
    let totalNew = 0;
    for (let i = 0; i < docs.length; i++) {
      const doc = docs[i];
      setProgress(true, `Extracting from ${doc.name} (${i + 1}/${docs.length})...`);
      await extractAndStoreForDoc(doc.id, doc.name, doc.type, doc.data);
      // Count new extractions by comparing before/after
    }
    await refreshTable();
    showToast('Bracket extraction complete.', 'success');
  } catch (err) {
    showToast('Extraction error: ' + err.message, 'error');
    console.error(err);
  } finally {
    setProgress(false);
  }
}

// ─── Apply All ───

/**
 * Applies all checked replacements to their respective documents in IndexedDB.
 */
async function handleApplyAll() {
  const replacements = await getAllReplacements();
  const active = replacements.filter((r) => r.active && r.replace);

  if (active.length === 0) {
    showToast('No active replacements with replacement text to apply.', 'warning');
    return;
  }

  setProgress(true, 'Applying replacements...');

  try {
    // Group by docId
    const byDoc = new Map();
    for (const r of active) {
      if (!byDoc.has(r.docId)) {
        byDoc.set(r.docId, []);
      }
      byDoc.get(r.docId).push({
        find: r.find,
        replace: r.replace,
        isBracket: r.source === 'auto'
      });
    }

    let count = 0;
    const total = byDoc.size;

    for (const [docId, reps] of byDoc) {
      count++;
      const doc = await getDocument(docId);
      if (!doc) continue;

      setProgress(true, `Applying to ${doc.name} (${count}/${total})...`);

      let newData;
      if (doc.type === 'docx') {
        newData = await applyDocxCleanReplacements(doc.data, reps);
      } else {
        // For PDF, we import dynamically
        const { applyPdfCleanReplacements } = await import('./pdf-processor.js');
        newData = await applyPdfCleanReplacements(doc.data, reps);
      }

      doc.data = newData;
      doc.size = newData.byteLength;

      // Use updateDocument from storage
      const { updateDocument } = await import('./storage.js');
      await updateDocument(doc);
    }

    await refreshDocList();
    showToast(`Applied replacements to ${total} document(s).`, 'success');
  } catch (err) {
    showToast('Apply error: ' + err.message, 'error');
    console.error(err);
  } finally {
    setProgress(false);
  }
}

// ─── Export Handlers ───

/**
 * Wraps an export function with progress overlay and error handling.
 * @param {Function} exportFn - The export function to call.
 * @param {string} label - Label for the operation.
 */
async function handleExport(exportFn, label) {
  setProgress(true, `Preparing ${label}...`);
  try {
    const count = await exportFn((msg) => setProgress(true, msg));
    showToast(`${label}: ${count} document(s) exported.`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
    console.error(err);
  } finally {
    setProgress(false);
  }
}

// ─── Event Wiring ───

/**
 * Initializes the application: opens DB, loads data, wires all event handlers.
 */
async function init() {
  try {
    await openDb();
  } catch (err) {
    showToast('Failed to open database: ' + err.message, 'error');
    return;
  }

  await refreshDocList();
  await refreshTable();

  // Upload: drag and drop
  uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('drag-over');
  });

  uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('drag-over');
  });

  uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
    handleUpload(e.dataTransfer.files);
  });

  // Upload: click to browse
  browseLink.addEventListener('click', (e) => {
    e.preventDefault();
    fileInput.click();
  });

  uploadArea.addEventListener('click', (e) => {
    if (e.target !== browseLink) {
      fileInput.click();
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      handleUpload(fileInput.files);
      fileInput.value = '';
    }
  });

  // Table filter
  tableFilter.addEventListener('input', applyFilter);

  // Check all toggle
  checkAll.addEventListener('change', async () => {
    const checked = checkAll.checked;
    const replacements = await getAllReplacements();
    for (const r of replacements) {
      r.active = checked;
      await updateReplacement(r);
    }
    await refreshTable();
  });

  // Add row
  btnAddRow.addEventListener('click', handleAddRow);

  // Extract all brackets
  btnExtractAll.addEventListener('click', handleExtractAll);

  // Apply all
  btnApplyAll.addEventListener('click', handleApplyAll);

  // Export buttons
  btnExportClean.addEventListener('click', () => {
    handleExport(exportCleanIndividual, 'Clean (Individual)');
  });

  btnExportCleanZip.addEventListener('click', () => {
    handleExport(exportCleanZip, 'Clean (Zip)');
  });

  btnExportRedline.addEventListener('click', () => {
    handleExport(exportRedlineIndividual, 'Redlines (Individual)');
  });

  btnExportRedlineZip.addEventListener('click', () => {
    handleExport(exportRedlineZip, 'Redlines (Zip)');
  });
}

// ─── Start ───
init();
