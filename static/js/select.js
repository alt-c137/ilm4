/* Свои списки вместо системных <select> — везде, и на ПК, и на телефоне (системный выглядит чужеродно).
   На ПК — выпадающая панель под кнопкой; на телефоне — панель снизу с точками выбора, как в Telegram.
   Настоящий <select> остаётся в форме: мы только рисуем его по-своему. Не трогаем: multiple, size > 1, data-native. */
(function () {
  var fine = window.matchMedia ? window.matchMedia('(hover:hover) and (pointer:fine)') : null;
  function sheetMode() { return window.innerWidth <= 760 || !(fine && fine.matches); }
  var open = null, sheet = null;
  function close() {
    if (open) { open.pop.hidden = true; open.btn.setAttribute('aria-expanded', 'false'); open = null; }
    if (sheet) { sheet.remove(); sheet = null; document.removeEventListener('keydown', onKey); }
  }
  function onKey(e) { if (e.key === 'Escape') close(); }
  function titleOf(sel) {
    var lab = sel.id ? document.querySelector('label[for="' + sel.id + '"]') : null;
    if (lab) return lab.textContent.trim();
    if (sel.getAttribute('aria-label')) return sel.getAttribute('aria-label');
    if (sel.dataset.title) return sel.dataset.title;
    var row = sel.closest('.tgs__row'); var b = row ? row.querySelector('b') : null;
    return b ? b.textContent.trim() : '';
  }
  function enhance(sel) {
    if (sel.multiple || sel.size > 1 || 'native' in sel.dataset) return;
    if (sel.dataset.sx) {                                // уже оформлен… или это копия оформленного (cloneNode): у копии кнопка «мёртвая»
      var was = sel.parentNode;
      if (!was || !was.classList.contains('sx') || was._sx) return;
      was.parentNode.insertBefore(sel, was); was.remove();
    }
    sel.dataset.sx = '1';
    var wrap = document.createElement('span'); wrap.className = 'sx'; wrap._sx = true;
    var btn = document.createElement('button'); btn.type = 'button'; btn.className = 'sx__btn'; btn.setAttribute('aria-haspopup', 'listbox'); btn.setAttribute('aria-expanded', 'false');
    var pop = document.createElement('div'); pop.className = 'sx__pop'; pop.hidden = true; pop.setAttribute('role', 'listbox');
    sel.parentNode.insertBefore(wrap, sel); wrap.appendChild(sel); wrap.appendChild(btn); wrap.appendChild(pop);
    if (sel.id) { btn.id = sel.id + '-sx'; var lab = document.querySelector('label[for="' + sel.id + '"]'); if (lab) lab.addEventListener('click', function (e) { e.preventDefault(); btn.focus(); }); }
    function label() { var o = sel.options[sel.selectedIndex]; btn.textContent = o ? o.textContent : ''; btn.classList.toggle('is-empty', !o || !o.value); btn.disabled = sel.disabled; }
    function build() {
      pop.innerHTML = '';
      Array.prototype.forEach.call(sel.options, function (o, i) {
        var it = document.createElement('div'); it.className = 'sx__i' + (i === sel.selectedIndex ? ' on' : '') + (o.disabled ? ' is-off' : '');
        it.setAttribute('role', 'option'); it.dataset.i = i; it.textContent = o.textContent; pop.appendChild(it);
      });
    }
    function pick(i) { if (sel.options[i] && !sel.options[i].disabled) { sel.selectedIndex = i; sel.dispatchEvent(new Event('change', { bubbles: true })); } label(); }
    function showSheet() {
      close();
      sheet = document.createElement('div'); sheet.className = 'sxs';
      var panel = document.createElement('div'); panel.className = 'sxs__p'; panel.setAttribute('role', 'listbox');
      var grip = document.createElement('div'); grip.className = 'sxs__grip'; panel.appendChild(grip);
      var title = titleOf(sel);
      if (title) { var t = document.createElement('div'); t.className = 'sxs__t'; t.textContent = title; panel.appendChild(t); }
      var list = document.createElement('div'); list.className = 'sxs__l';
      Array.prototype.forEach.call(sel.options, function (o, i) {
        var it = document.createElement('button'); it.type = 'button';
        it.className = 'sxs__i' + (i === sel.selectedIndex ? ' on' : '') + (o.disabled ? ' is-off' : '');
        it.setAttribute('role', 'option'); it.dataset.i = i;
        var dot = document.createElement('i'); var tx = document.createElement('span'); tx.textContent = o.textContent;
        it.appendChild(dot); it.appendChild(tx); list.appendChild(it);
      });
      panel.appendChild(list); sheet.appendChild(panel); document.body.appendChild(sheet);
      sheet.addEventListener('click', function (e) {
        var it = e.target.closest('.sxs__i');
        if (it) { pick(+it.dataset.i); close(); return; }
        if (e.target === sheet) close();
      });
      document.addEventListener('keydown', onKey);
      var cur = list.querySelector('.on'); if (cur) cur.scrollIntoView({ block: 'center' });
    }
    function show() {
      if (sheetMode()) { showSheet(); return; }
      close(); build(); pop.hidden = false; btn.setAttribute('aria-expanded', 'true'); open = { pop: pop, btn: btn };
      var r = wrap.getBoundingClientRect(); pop.classList.toggle('sx__pop--up', window.innerHeight - r.bottom < 260 && r.top > 260);
      var cur = pop.querySelector('.on'); if (cur) cur.scrollIntoView({ block: 'nearest' });
    }
    btn.addEventListener('click', function () { if (open && open.pop === pop) close(); else show(); });
    pop.addEventListener('click', function (e) { var it = e.target.closest('.sx__i'); if (!it) return; pick(+it.dataset.i); close(); btn.focus(); });
    var typed = '', typedT = 0;
    btn.addEventListener('keydown', function (e) {
      var n = sel.options.length, i = sel.selectedIndex;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); pick(Math.max(0, Math.min(n - 1, i + (e.key === 'ArrowDown' ? 1 : -1)))); if (open) build(); }
      else if (e.key === 'Escape') close();
      else if (e.key.length === 1 && e.key !== ' ') {
        clearTimeout(typedT); typed += e.key.toLowerCase(); typedT = setTimeout(function () { typed = ''; }, 700);
        for (var k = 0; k < n; k++) if (sel.options[k].textContent.trim().toLowerCase().indexOf(typed) === 0) { pick(k); if (open) build(); break; }
      }
    });
    sel.addEventListener('change', label);
    label();
  }
  function scan(root) { (root || document).querySelectorAll('select').forEach(enhance); }
  document.addEventListener('click', function (e) { if (open && !e.target.closest('.sx')) close(); });
  // строка настройки целиком открывает свой список (нажал на «Кто видит мой номер» — выбрал), как в Telegram
  document.addEventListener('click', function (e) {
    var row = e.target.closest('.tgs__row'); if (!row || e.target.closest('.sx')) return;
    var b = row.querySelector('.sx__btn'); if (b && !b.disabled) { e.preventDefault(); b.click(); }
  });
  window.addEventListener('scroll', function (e) { if (open && !(e.target.closest && e.target.closest('.sx__pop'))) close(); }, true);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { scan(); }); else scan();
  new MutationObserver(function (list) { list.forEach(function (m) { m.addedNodes.forEach(function (n) { if (n.nodeType === 1) { if (n.tagName === 'SELECT') enhance(n); else if (n.querySelector) scan(n); } }); }); })
    .observe(document.documentElement, { childList: true, subtree: true });
})();
