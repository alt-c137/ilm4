/* Карта ilm4: Leaflet (свой, не с CDN) + подложка с автоматическим запасным вариантом.
 *
 * Порядок подложек: MapTiler (если в админке задан ключ) → OpenStreetMap → Esri.
 * (CARTO убран: без ключа рисует поверх карты «API KEY REQUIRED».)
 * Если текущая подложка не отдаёт плитки (сервис недоступен, лимит, блокировка) —
 * карта сама переключается на следующую, пользователь видит карту, а не серое поле.
 *
 * Использование: var map = ilmMap('map', {center: [41.31, 69.28], zoom: 12});
 * Настройки приходят из <script id="map-cfg" type="application/json">.
 */
(function () {
  function cfg() {
    var el = document.getElementById('map-cfg');
    try { return el ? JSON.parse(el.textContent) : {}; } catch (e) { return {}; }
  }

  function providers(c, dark) {
    var list = [];
    if (c.maptiler) {
      list.push({
        name: 'maptiler',
        url: 'https://api.maptiler.com/maps/' + (dark ? 'streets-v2-dark' : 'streets-v2') + '/256/{z}/{x}/{y}.png?key=' + encodeURIComponent(c.maptiler),
        opt: { maxZoom: 20, attribution: '<a href="https://www.maptiler.com/copyright/" target="_blank" rel="noopener">© MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap</a>' }
      });
    }
    list.push({
      name: 'osm',
      url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      opt: { maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>' }
    });
    list.push({
      name: 'esri',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
      opt: { maxZoom: 19, attribution: 'Tiles © <a href="https://www.esri.com/" target="_blank" rel="noopener">Esri</a>' }
    });
    return list;
  }

  window.ilmMap = function (id, options) {
    options = options || {};
    var c = cfg();
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    var map = L.map(id, { zoomControl: options.zoomControl !== false, scrollWheelZoom: options.scrollWheelZoom !== false })
      .setView(options.center || [41.3111, 69.2797], options.zoom || 6);
    var chain = providers(c, dark), i = 0, layer = null;

    function use(n) {
      if (layer) map.removeLayer(layer);
      var p = chain[n], ok = 0, bad = 0;
      layer = L.tileLayer(p.url, p.opt);
      layer.on('tileload', function () { ok++; });
      layer.on('tileerror', function () {
        bad++;
        // много ошибок и почти ни одной загрузки — подложка недоступна, берём следующую
        if (bad >= 4 && ok < 2 && i < chain.length - 1) { i++; use(i); }
      });
      layer.addTo(map);
      map.getContainer().setAttribute('data-tiles', p.name);
    }
    use(0);
    return map;
  };

})();
