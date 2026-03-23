/**
 * storage.js — IndexedDB persistence for documents and replacements.
 * DB name: docReplacer, version 1.
 * Stores: documents (ArrayBuffers), replacements (find/replace pairs).
 */

const DB_NAME = 'docReplacer';
const DB_VERSION = 1;

let dbInstance = null;

/**
 * Opens (or creates) the IndexedDB database.
 * @returns {Promise<IDBDatabase>} The database instance.
 */
export function openDb() {
  if (dbInstance) {
    return Promise.resolve(dbInstance);
  }
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('documents')) {
        db.createObjectStore('documents', { keyPath: 'id', autoIncrement: true });
      }
      if (!db.objectStoreNames.contains('replacements')) {
        const store = db.createObjectStore('replacements', { keyPath: 'id', autoIncrement: true });
        store.createIndex('byDocId', 'docId', { unique: false });
      }
    };
    request.onsuccess = (event) => {
      dbInstance = event.target.result;
      resolve(dbInstance);
    };
    request.onerror = (event) => {
      reject(new Error('Failed to open IndexedDB: ' + event.target.error));
    };
  });
}

/**
 * Adds a document record to IndexedDB.
 * @param {Object} doc - { name, type, data: ArrayBuffer, size, dateAdded }
 * @returns {Promise<number>} The auto-generated id.
 */
export function addDocument(doc) {
  return openDb().then((db) => {
    return new Promise((resolve, reject) => {
      const tx = db.transaction('documents', 'readwrite');
      const store = tx.objectStore('documents');
      const request = store.add(doc);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error('Failed to add document: ' + request.error));
    });
  });
}

/**
 * Gets all documents from IndexedDB.
 * @returns {Promise<Array>} Array of document records.
 */
export function getAllDocuments() {
  return openDb().then((db) => {
    return new Promise((resolve, reject) => {
      const tx = db.transaction('documents', 'readonly');
      const store = tx.objectStore('documents');
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error('Failed to get documents: ' + request.error));
    });
  });
}

/**
 * Gets a single document by id.
 * @param {number} id - Document id.
 * @returns {Promise<Object>} The document record.
 */
export function getDocument(id) {
  return openDb().then((db) => {
    return new Promise((resolve, reject) => {
      const tx = db.transaction('documents', 'readonly');
      const store = tx.objectStore('documents');
      const request = store.get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error('Failed to get document: ' + request.error));
    });
  });
}

/**
 * Updates a document record in IndexedDB (replaces the whole record).
 * @param {Object} doc - Full document record including id.
 * @returns {Promise<void>}
 */
export function updateDocument(doc) {
  return openDb().then((db) => {
    return new Promise((resolve, reject) => {
      const tx = db.transaction('documents', 'readwrite');
      const store = tx.objectStore('documents');
      const request = store.put(doc);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(new Error('Failed to update document: ' + request.error));
    });
  });
}

/**
 * Deletes a document by id.
 * @param {number} id - Document id.
 * @returns {Promise<void>}
 */
export function deleteDocument(id) {
  return openDb().then((db) => {
    return new Promise((resolve, reject) => {
      const tx = db.transaction('documents', 'readwrite');
      const store = tx.objectStore('documents');
      const request = store.delete(id);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(new Error('Failed to delete document: ' + request.error));
    });
  });
}

/**
 * Adds a replacement record to IndexedDB.
 * @param {Object} replacement - { docId, docName, find, replace, source, active }
 * @returns {Promise<number>} The auto-generated id.
 */
export function addReplacement(replacement) {
  return openDb().then((db) => {
    return new Promise((resolve, reject) => {
      const tx = db.transaction('replacements', 'readwrite');
      const store = tx.objectStore('replacements');
      const request = store.add(replacement);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error('Failed to add replacement: ' + request.error));
    });
  });
}

/**
 * Gets all replacement records.
 * @returns {Promise<Array>} Array of replacement records.
 */
export function getAllReplacements() {
  return openDb().then((db) => {
    return new Promise((resolve, reject) => {
      const tx = db.transaction('replacements', 'readonly');
      const store = tx.objectStore('replacements');
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error('Failed to get replacements: ' + request.error));
    });
  });
}

/**
 * Gets all replacements for a specific document.
 * @param {number} docId - Document id.
 * @returns {Promise<Array>} Array of replacement records.
 */
export function getReplacementsByDocId(docId) {
  return openDb().then((db) => {
    return new Promise((resolve, reject) => {
      const tx = db.transaction('replacements', 'readonly');
      const store = tx.objectStore('replacements');
      const index = store.index('byDocId');
      const request = index.getAll(docId);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error('Failed to get replacements by docId: ' + request.error));
    });
  });
}

/**
 * Updates a replacement record.
 * @param {Object} replacement - Full replacement record including id.
 * @returns {Promise<void>}
 */
export function updateReplacement(replacement) {
  return openDb().then((db) => {
    return new Promise((resolve, reject) => {
      const tx = db.transaction('replacements', 'readwrite');
      const store = tx.objectStore('replacements');
      const request = store.put(replacement);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(new Error('Failed to update replacement: ' + request.error));
    });
  });
}

/**
 * Deletes a replacement by id.
 * @param {number} id - Replacement id.
 * @returns {Promise<void>}
 */
export function deleteReplacement(id) {
  return openDb().then((db) => {
    return new Promise((resolve, reject) => {
      const tx = db.transaction('replacements', 'readwrite');
      const store = tx.objectStore('replacements');
      const request = store.delete(id);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(new Error('Failed to delete replacement: ' + request.error));
    });
  });
}

/**
 * Deletes all replacements for a specific document.
 * @param {number} docId - Document id.
 * @returns {Promise<void>}
 */
export function deleteReplacementsByDocId(docId) {
  return getReplacementsByDocId(docId).then((replacements) => {
    return openDb().then((db) => {
      const tx = db.transaction('replacements', 'readwrite');
      const store = tx.objectStore('replacements');
      const promises = replacements.map((r) => {
        return new Promise((resolve, reject) => {
          const request = store.delete(r.id);
          request.onsuccess = () => resolve();
          request.onerror = () => reject(request.error);
        });
      });
      return Promise.all(promises);
    });
  });
}
