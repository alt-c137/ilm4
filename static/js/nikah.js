/* Никях: выбор страны и города из списка (по алфавиту, с поиском по буквам).
 * <div class="nkpick" data-pick="country"><input name="country"></div>
 * <div class="nkpick" data-pick="city" data-country="country"><input name="city"></div>
 * Данные — <script id="nk-geo" type="application/json">{countries:[…], cities:{страна:[…]}}.
 * Город можно вписать и свой: список — подсказка. */
(function () {
  var el = document.getElementById('nk-geo');
  if (!el) return;
  var GEO; try { GEO = JSON.parse(el.textContent); } catch (e) { return; }
  function norm(s) { return (s || '').toLowerCase().replace(/ё/g, 'е').trim(); }

  document.querySelectorAll('.nkpick').forEach(function (box) {
    var input = box.querySelector('input'), list = document.createElement('div');
    list.className = 'nkpick__list'; list.hidden = true; box.appendChild(list);
    var isCity = box.dataset.pick === 'city';
    function countryInput() { return box.closest('form').querySelector('[name=' + (box.dataset.country || 'country') + ']'); }
    function source() {
      if (!isCity) return GEO.countries;
      var c = countryInput(); if (!c || !c.value) return null;
      var key = Object.keys(GEO.cities).filter(function (k) { return norm(k) === norm(c.value); })[0];
      return key ? GEO.cities[key] : [];
    }
    function placeholder() {
      if (!isCity) return;
      var c = countryInput();
      input.placeholder = c && c.value ? 'Выберите или впишите город' : 'Сначала укажите страну';
    }
    function render() {
      var items = source(), q = norm(input.value), html = '';
      if (items === null) { list.innerHTML = '<p class="nkpick__hint">Сначала выберите страну</p>'; list.hidden = false; return; }
      var starts = [], has = [];
      items.forEach(function (it) { var n = norm(it); if (!q || n.indexOf(q) === 0) starts.push(it); else if (n.indexOf(q) > 0) has.push(it); });
      var all = starts.concat(has).slice(0, 300);
      all.forEach(function (it) { html += '<button type="button" class="nkpick__i">' + it.replace(/[&<>"]/g, function (ch) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[ch]; }) + '</button>'; });
      if (!all.length) html = '<p class="nkpick__hint">' + (isCity ? 'Нет в списке — впишите свой город' : 'Страна не найдена') + '</p>';
      list.innerHTML = html; list.hidden = false;
    }
    function pick(v) {
      input.value = v; list.hidden = true;
      input.dispatchEvent(new Event('input', {bubbles: true})); input.dispatchEvent(new Event('change', {bubbles: true}));
      if (!isCity) { var city = box.closest('form').querySelector('.nkpick[data-pick=city] input'); if (city) { city.value = ''; city.dispatchEvent(new Event('focus')); } }
    }
    input.setAttribute('autocomplete', 'off');
    input.addEventListener('focus', render);
    input.addEventListener('input', render);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !list.hidden) {
        var first = list.querySelector('.nkpick__i');
        e.preventDefault(); e.stopPropagation();
        if (first && input.value) pick(first.textContent); else list.hidden = true;
      } else if (e.key === 'Escape') list.hidden = true;
    });
    list.addEventListener('mousedown', function (e) { e.preventDefault(); });   // не терять фокус до клика
    list.addEventListener('click', function (e) { var b = e.target.closest('.nkpick__i'); if (b) pick(b.textContent); });
    input.addEventListener('blur', function () { setTimeout(function () { list.hidden = true; }, 120); });
    if (isCity) { var c = countryInput(); if (c) c.addEventListener('change', placeholder); placeholder(); }
  });
})();
