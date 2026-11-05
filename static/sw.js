// An explicit public allowlist. NEVER runtime-cache navigation or private responses.
const CACHE = 'careloop-public-v3';
const PUBLIC_ASSETS = ['/static/app.css', '/static/app.js', '/static/theme.js', '/static/offline.html', '/static/icon-192.png', '/static/icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PUBLIC_ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (PUBLIC_ASSETS.includes(url.pathname) && !url.search) {
    event.respondWith(fetch(event.request, {cache: 'no-store'}).catch(() => caches.match(url.pathname)));
  } else if (event.request.mode === 'navigate') {
    // Network only; the sole offline fallback contains no user data.
    event.respondWith(fetch(event.request, {cache: 'no-store'}).catch(() => caches.match('/static/offline.html')));
  }
});
