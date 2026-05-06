/* Detective Conan TCG · Case File — Service Worker
 * - Pre-caches the app shell on install
 * - Runtime-caches card images (cache-first, opaque OK) from laststand.co.th
 * - Network-first for resync API; falls back to cache for offline browsing
 */
const VERSION = 'conan-tcg-v3';
const SHELL_CACHE = `${VERSION}-shell`;
const IMAGE_CACHE = `${VERSION}-images`;
const RUNTIME_CACHE = `${VERSION}-runtime`;

const SHELL_URLS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './icon-512-maskable.png',
  './apple-touch-icon.png',
  './favicon-32.png'
];

const IMG_HOST = 'laststand.co.th';

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(SHELL_CACHE).then((cache) =>
      // Use individual adds so a single 404 (e.g. an icon a user hasn't deployed) won't break install
      Promise.all(
        SHELL_URLS.map((u) =>
          cache.add(new Request(u, { cache: 'reload' })).catch(() => {})
        )
      )
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const { request } = e;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // 1) Card images on laststand.co.th — cache-first, store opaque responses
  if (url.hostname.endsWith(IMG_HOST) && url.pathname.startsWith('/media/conan_card/')) {
    e.respondWith(
      caches.open(IMAGE_CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        if (cached) return cached;
        try {
          // no-cors lets us cache the image even without CORS headers (opaque response)
          const res = await fetch(request, { mode: 'no-cors' });
          // Only cache successful or opaque responses
          if (res && (res.ok || res.type === 'opaque')) {
            cache.put(request, res.clone());
          }
          return res;
        } catch (err) {
          // Offline + no cache — let the browser show its broken-image icon
          return Response.error();
        }
      })
    );
    return;
  }

  // 2) Search/sync endpoint — network-first, fall back to cache
  if (url.hostname.endsWith(IMG_HOST) && url.pathname.startsWith('/cc_search')) {
    e.respondWith(
      fetch(request).then((res) => {
        const clone = res.clone();
        caches.open(RUNTIME_CACHE).then((c) => c.put(request, clone));
        return res;
      }).catch(() => caches.match(request))
    );
    return;
  }

  // 3) Same-origin app shell — cache-first, falling back to network
  if (url.origin === self.location.origin) {
    e.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((res) => {
          // Don't cache non-OK responses or POSTs
          if (!res || !res.ok || res.type !== 'basic') return res;
          const clone = res.clone();
          caches.open(SHELL_CACHE).then((c) => c.put(request, clone));
          return res;
        }).catch(() => caches.match('./index.html'));
      })
    );
    return;
  }

  // 4) Everything else (Google Fonts, etc.) — stale-while-revalidate
  e.respondWith(
    caches.open(RUNTIME_CACHE).then(async (cache) => {
      const cached = await cache.match(request);
      const networkPromise = fetch(request).then((res) => {
        if (res && (res.ok || res.type === 'opaque')) cache.put(request, res.clone());
        return res;
      }).catch(() => cached);
      return cached || networkPromise;
    })
  );
});

// Handle messages from the page (e.g. for clearing caches or warming image cache)
self.addEventListener('message', (e) => {
  const msg = e.data || {};
  if (msg.type === 'WARM_IMAGE_CACHE' && Array.isArray(msg.urls)) {
    e.waitUntil(
      caches.open(IMAGE_CACHE).then(async (cache) => {
        let done = 0;
        for (const u of msg.urls) {
          try {
            const req = new Request(u, { mode: 'no-cors' });
            const cached = await cache.match(req);
            if (cached) { done++; continue; }
            const res = await fetch(req);
            if (res && (res.ok || res.type === 'opaque')) {
              await cache.put(req, res.clone());
            }
            done++;
            if (done % 5 === 0 || done === msg.urls.length) {
              const cs = await self.clients.matchAll();
              cs.forEach((c) => c.postMessage({ type: 'WARM_PROGRESS', done, total: msg.urls.length }));
            }
          } catch {/* ignore */}
        }
        const cs = await self.clients.matchAll();
        cs.forEach((c) => c.postMessage({ type: 'WARM_DONE', done, total: msg.urls.length }));
      })
    );
  }
  if (msg.type === 'CLEAR_IMAGE_CACHE') {
    e.waitUntil(caches.delete(IMAGE_CACHE));
  }
  if (msg.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
