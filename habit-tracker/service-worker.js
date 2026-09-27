const CACHE_NAME = 'habit-tracker-v4';
const BASE = self.registration.scope;
const ASSETS = [
  '',
  'index.html',
  'css/styles.css',
  'js/app.js',
  'js/data.js',
  'js/daily-view.js',
  'js/grid-view.js',
  'js/stats-view.js',
  'js/habit-editor.js',
  'manifest.json',
  'icons/icon-192.png',
  'icons/icon-512.png',
].map(p => BASE + p);

// Install: pre-cache all assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

/**
 * Fetches from the network and stores a successful copy in the cache.
 * @param {FetchEvent} event - The fetch event (keeps the worker alive for the cache write).
 * @param {Request} request - The request to fetch.
 * @returns {Promise<Response>} The network response.
 */
function fetchAndCache(event, request) {
  // 'no-cache' revalidates with the server (cheap 304s) instead of reusing a
  // possibly stale HTTP-cache copy, so deploys reach the SW cache promptly.
  return fetch(request, { cache: 'no-cache' }).then((response) => {
    if (response.ok) {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.put(request, copy)));
    }
    return response;
  });
}

// Fetch strategy (same-origin GETs only):
// - Page navigations: network-first, so new deploys show up on the next load;
//   fall back to the cached page when offline.
// - Other app-shell assets: stale-while-revalidate, so they load instantly
//   from cache while the cache is refreshed in the background.
self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) {
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetchAndCache(event, request).catch(() =>
        caches.match(request).then((cached) => cached || caches.match(BASE + 'index.html'))
      )
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetchAndCache(event, request);
      if (cached) {
        event.waitUntil(network.catch(() => {}));
        return cached;
      }
      return network;
    })
  );
});
