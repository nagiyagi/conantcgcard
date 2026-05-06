/* Case File - Conan TCG Tracker - Service Worker
   Strategy:
   - App shell (index.html, manifest, icons): cache-first with network fallback
   - Card data (data/cards.json): network-first (so updates flow), cache fallback
   - Card images (Takara Tomy CDN): cache-first, lazy populated as users view them
*/

const VERSION = 'v1.0.0';
const SHELL_CACHE = `casefile-shell-${VERSION}`;
const DATA_CACHE = `casefile-data-${VERSION}`;
const IMG_CACHE = `casefile-images-${VERSION}`;

const SHELL_URLS = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon.svg',
  './icons/icon-192.png',
  './icons/icon-512.png',
];

const IMAGE_HOSTS = [
  'www.takaratomy.co.jp',
  'takaratomy.co.jp',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then(cache => cache.addAll(SHELL_URLS).catch(err => {
        // Don't fail install if optional assets are missing
        console.warn('SW: some shell assets missing', err);
      }))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => !k.endsWith(VERSION)).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Card images from Takara Tomy: cache-first
  if (IMAGE_HOSTS.includes(url.hostname)) {
    event.respondWith(cacheFirst(req, IMG_CACHE));
    return;
  }

  // Card data: network-first (so updates propagate), then cache
  if (url.pathname.endsWith('/data/cards.json')) {
    event.respondWith(networkFirst(req, DATA_CACHE));
    return;
  }

  // App shell: cache-first
  if (url.origin === location.origin) {
    event.respondWith(cacheFirst(req, SHELL_CACHE));
    return;
  }
});

async function cacheFirst(req, cacheName) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (res.ok) {
      const cache = await caches.open(cacheName);
      cache.put(req, res.clone());
    }
    return res;
  } catch (e) {
    // Final fallback: return cached match for any URL (may be undefined)
    return cached || new Response('', { status: 504, statusText: 'Offline' });
  }
}

async function networkFirst(req, cacheName) {
  try {
    const res = await fetch(req);
    if (res.ok) {
      const cache = await caches.open(cacheName);
      cache.put(req, res.clone());
    }
    return res;
  } catch (e) {
    const cached = await caches.match(req);
    if (cached) return cached;
    return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
  }
}
