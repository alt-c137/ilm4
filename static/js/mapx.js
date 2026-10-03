/* ilm4 · карта халяль как в навигаторах: метки по видимой области, значки категорий, группировка близких меток,
   поиск, категории, «Проверенные», «где я», список мест сбоку/снизу с расстоянием и маршрутом. */
(function () {
  'use strict';
  var box = document.getElementById('mapx');
  if (!box || !window.ilmMap) return;
  function T(s) { return window._t ? window._t(s) : s; }
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; }
  var map = ilmMap('map', { center: [41.3111, 69.2797], zoom: 12, zoomControl: false });
  L.control.zoom({ position: 'bottomleft' }).addTo(map);
  var layer = L.layerGroup().addTo(map), meMarker = null, me = null;
  var state = { cat: box.dataset.cat || '', q: box.dataset.q || '', verified: false, items: [], selected: null };
  var list = document.getElementById('mapx-list'), count = document.getElementById('mapx-count');
  var panel = document.getElementById('mapx-panel');

  function km(a, b) {
    var R = 6371, dLat = (b.lat - a.lat) * Math.PI / 180, dLon = (b.lon - a.lon) * Math.PI / 180;
    var x = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a.lat * Math.PI / 180) * Math.cos(b.lat * Math.PI / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
  }
  function dist(p) {
    var from = me || { lat: map.getCenter().lat, lon: map.getCenter().lng };
    var d = km(from, p);
    return d < 1 ? Math.round(d * 1000) + ' ' + T('м') : (d < 10 ? d.toFixed(1) : Math.round(d)) + ' ' + T('км');
  }
  function route(p) {
    // маршрут — в привычном навигаторе: на iPhone — Карты Apple, иначе — Google Maps
    var ll = p.lat + ',' + p.lon;
    return /iPhone|iPad|Mac/.test(navigator.userAgent) ? 'https://maps.apple.com/?daddr=' + ll : 'https://www.google.com/maps/dir/?api=1&destination=' + ll;
  }

  /* ---------- метки: значок категории; близкие друг к другу — одним кружком с числом ---------- */
  var IC = {}; try { IC = JSON.parse(document.getElementById('ui-icons').textContent); } catch (e) { /* значков нет — метка без рисунка */ }
  function glyph(p) { return IC[p.icon] || IC.place || ''; }
  function pin(p) {
    var cls = 'mpin mpin--' + esc(p.kind) + (p.verif === 'ilm4' ? ' mpin--ok' : '') + (state.selected === p.id ? ' on' : '');
    return L.divIcon({ className: '', html: '<div class="' + cls + '"><span>' + glyph(p) + '</span></div>', iconSize: [38, 44], iconAnchor: [19, 42] });
  }
  function draw() {
    layer.clearLayers();
    var cell = 54, groups = {};
    state.items.forEach(function (p) {
      var pt = map.latLngToContainerPoint([p.lat, p.lon]);
      var k = Math.floor(pt.x / cell) + ':' + Math.floor(pt.y / cell);
      (groups[k] = groups[k] || []).push(p);
    });
    Object.keys(groups).forEach(function (k) {
      var g = groups[k];
      if (g.length === 1 || map.getZoom() >= 17) {
        g.forEach(function (p) {
          L.marker([p.lat, p.lon], { icon: pin(p), riseOnHover: true }).addTo(layer)
            .on('click', function () { select(p.id, true); });
        });
        return;
      }
      var lat = 0, lon = 0;
      g.forEach(function (p) { lat += p.lat; lon += p.lon; });
      lat /= g.length; lon /= g.length;
      L.marker([lat, lon], { icon: L.divIcon({ className: '', html: '<div class="mclu">' + g.length + '</div>', iconSize: [44, 44], iconAnchor: [22, 22] }) })
        .addTo(layer).on('click', function () {
          map.fitBounds(L.latLngBounds(g.map(function (p) { return [p.lat, p.lon]; })), { padding: [60, 60], maxZoom: 17 });
        });
    });
  }

  /* ---------- список ---------- */
  function render() {
    var items = state.items.slice();
    var c = map.getCenter(), from = me || { lat: c.lat, lon: c.lng };
    items.sort(function (a, b) { return km(from, a) - km(from, b); });
    count.textContent = items.length ? T('Мест:') + ' ' + items.length : T('Здесь пока ничего нет');
    if (!items.length) {
      list.innerHTML = '<div class="mapx__empty">' + T('Отдалите карту или выберите другую категорию. Знаете место? Добавьте его — кнопка «+».') + '</div>';
      return;
    }
    list.innerHTML = items.slice(0, 120).map(function (p) {
      return '<div class="mapx__item' + (state.selected === p.id ? ' on' : '') + '" data-id="' + p.id + '">' +
        '<span class="mapx__ic mapx__ic--' + esc(p.kind) + '">' + glyph(p) + '</span>' +
        '<span class="mapx__ib"><b>' + esc(p.name) + '</b><small>' + esc(p.category) + (p.address ? ' · ' + esc(p.address) : ' · ' + esc(p.city)) + '</small>' +
        (p.brief ? '<small class="mapx__brief">' + esc(p.brief) + '</small>' : '') +
        '<span class="vbadge vbadge--' + esc(p.verif) + '">' + esc(p.verif_label) + '</span></span>' +
        '<span class="mapx__ia"><em>' + dist(p) + '</em><a class="mapx__go" href="' + route(p) + '" target="_blank" rel="noopener" title="' + T('Маршрут') + '">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l18-8-8 18-2-8z"/></svg></a></span></div>';
    }).join('');
  }
  function select(id, fromMap) {
    state.selected = id; draw(); render();
    var el = list.querySelector('[data-id="' + id + '"]');
    if (el) { panel.classList.add('is-open'); el.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
    var p = state.items.filter(function (x) { return x.id === id; })[0];
    if (p && !fromMap) map.setView([p.lat, p.lon], Math.max(map.getZoom(), 16));
  }
  list.addEventListener('click', function (e) {
    if (e.target.closest('.mapx__go')) return;
    var it = e.target.closest('.mapx__item[data-id]'); if (!it) return;
    var id = +it.dataset.id;
    if (state.selected === id) location.href = '/map/' + id + '/'; else select(id, false);
  });

  /* ---------- загрузка по видимой области ---------- */
  var timer = null, ctrl = null;
  function load() {
    clearTimeout(timer);
    timer = setTimeout(function () {
      var b = map.getBounds();
      var url = '/map/data/?bbox=' + [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()].map(function (x) { return x.toFixed(4); }).join(',') +
        '&category=' + encodeURIComponent(state.cat) + '&q=' + encodeURIComponent(state.q) + (state.verified ? '&verified=1' : '');
      if (ctrl) ctrl.abort();
      ctrl = window.AbortController ? new AbortController() : null;
      fetch(url, { credentials: 'same-origin', signal: ctrl && ctrl.signal }).then(function (r) { return r.json(); })
        .then(function (j) { state.items = j.items || []; draw(); render(); }).catch(function () {});
    }, 250);
  }
  map.on('moveend', load);
  map.on('zoomend', draw);

  /* ---------- поиск, категории, проверенные ---------- */
  var q = document.getElementById('mapx-q'), clear = document.getElementById('mapx-clear');
  document.getElementById('mapx-form').addEventListener('submit', function (e) { e.preventDefault(); state.q = q.value.trim(); load(); });
  q.addEventListener('input', function () { clear.hidden = !q.value; if (!q.value && state.q) { state.q = ''; load(); } });
  clear.addEventListener('click', function () { q.value = ''; clear.hidden = true; state.q = ''; load(); });
  document.getElementById('mapx-cats').addEventListener('click', function (e) {
    var b = e.target.closest('[data-cat]'); if (!b) return;
    state.cat = b.dataset.cat;
    this.querySelectorAll('[data-cat]').forEach(function (x) { x.classList.toggle('on', x === b); });
    load();
  });
  var ver = document.getElementById('mapx-verified');
  ver.addEventListener('click', function () { state.verified = !state.verified; ver.classList.toggle('on', state.verified); ver.setAttribute('aria-pressed', String(state.verified)); load(); });

  /* ---------- где я ---------- */
  function locate(silent) {
    if (!navigator.geolocation) { if (!silent) alert(T('Браузер не умеет определять местоположение')); return; }
    navigator.geolocation.getCurrentPosition(function (pos) {
      me = { lat: pos.coords.latitude, lon: pos.coords.longitude };
      if (meMarker) map.removeLayer(meMarker);
      meMarker = L.marker([me.lat, me.lon], { icon: L.divIcon({ className: '', html: '<div class="mme"></div>', iconSize: [20, 20], iconAnchor: [10, 10] }), interactive: false }).addTo(map);
      map.setView([me.lat, me.lon], 15);
    }, function () { if (!silent) alert(T('Не удалось получить координаты — разрешите доступ к геолокации')); }, { timeout: 8000 });
  }
  document.getElementById('mapx-me').addEventListener('click', function () { locate(false); });

  /* ---------- панель на телефоне: потянуть / нажать — развернуть ---------- */
  document.getElementById('mapx-grip').addEventListener('click', function () { panel.classList.toggle('is-open'); });

  /* ---------- старт: метки, что пришли со страницей; иначе — где я ---------- */
  var first = [];
  try { first = JSON.parse(document.getElementById('mapx-initial').textContent) || []; } catch (e) { first = []; }
  if (first.length > 1) map.fitBounds(first.map(function (m) { return [m.lat, m.lon]; }), { padding: [40, 40], maxZoom: 14 });
  else if (first.length === 1) map.setView([first[0].lat, first[0].lon], 14);
  else load();
  if (!first.length) locate(true);
})();
