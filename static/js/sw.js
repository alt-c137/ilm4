/* Service worker ilm4: сайт ставится на телефон как приложение; без сети — страница «Нет подключения».
   Страницы не кэшируем (всегда свежие), только офлайн-заглушку и иконки. */
var CACHE = 'ilm4-v1';
self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(['/offline/']); }));
  self.skipWaiting();
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }));
  self.clients.claim();
});
self.addEventListener('fetch', function (e) {
  if (e.request.mode !== 'navigate') return;          // только переходы по страницам
  e.respondWith(fetch(e.request).catch(function () { return caches.match('/offline/'); }));
});
