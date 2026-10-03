/* Свои выпадающие списки вместо системных (на ПК те выглядят чужеродно). На телефоне оставляем системный выбор —
   он удобнее пальцем (так же делает Telegram). Настоящий <select> остаётся в форме: мы только рисуем его по-своему.
   Не трогаем: multiple, size > 1, data-native. */
(function () {
  if (!window.matchMedia || !window.matchMedia('(hover:hover) and (pointer:fine)').matches) return;
  var open = null;
  function close() { if (open) { open.pop.hidden = true; open.btn.setAttribute('aria-expanded', 'false'); open = null; } }
  function enhance(sel) {
    if (sel.dataset.sx || sel.multiple || sel.size > 1 || 'native' in sel.dataset) return;
    sel.dataset.sx = '1';
    var wrap = document.createElement('span'); wrap.className = 'sx';
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
    function show() {
      close(); build(); pop.hidden = false; btn.setAttribute('aria-expanded', 'true'); open = { pop: pop, btn: btn };
      var r = wrap.getBoundingClientRect(); pop.classList.toggle('sx__pop--up', window.innerHeight - r.bottom < 260 && r.top > 260);
      var cur = pop.querySelector('.on'); if (cur) cur.scrollIntoView({ block: 'nearest' });
    }
    function pick(i) { if (sel.options[i] && !sel.options[i].disabled) { sel.selectedIndex = i; sel.dispatchEvent(new Event('change', { bubbles: true })); } label(); }
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
  window.addEventListener('scroll', function (e) { if (open && !(e.target.closest && e.target.closest('.sx__pop'))) close(); }, true);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { scan(); }); else scan();
  new MutationObserver(function (list) { list.forEach(function (m) { m.addedNodes.forEach(function (n) { if (n.nodeType === 1) { if (n.tagName === 'SELECT') enhance(n); else if (n.querySelector) scan(n); } }); }); })
    .observe(document.documentElement, { childList: true, subtree: true });
})();
