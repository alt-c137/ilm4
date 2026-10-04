/* Свой календарь и выбор времени вместо системных (input type=date / datetime-local / time).
   Настоящее поле остаётся в форме (становится скрытым) и хранит значение в прежнем виде: 2026-10-04, 2026-10-04T18:30, 18:30 —
   поэтому серверу и остальным скриптам ничего менять не нужно. Не трогаем поля с data-native. */
(function () {
  var LANG = document.documentElement.lang || 'ru';
  var T = window._t || function (s) { return s; };
  var CAL = '<svg viewBox="0 0 24 24"><rect x="4" y="5" width="16" height="15" rx="3"/><path d="M4 10h16M8.5 3v4M15.5 3v4"/></svg>';
  var CLK = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>';
  var PREV = '<svg viewBox="0 0 24 24"><path d="M14.5 6 8.5 12l6 6"/></svg>', NEXT = '<svg viewBox="0 0 24 24"><path d="m9.5 6 6 6-6 6"/></svg>';
  var VALUE = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function iso(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function parse(v) {                                   // «2026-10-04», «2026-10-04T18:30», «18:30» → {d: Date|null, h, m}
    var out = { d: null, h: null, m: null }, s = String(v || '');
    var dm = s.match(/^(\d{4})-(\d{2})-(\d{2})/); if (dm) out.d = new Date(+dm[1], +dm[2] - 1, +dm[3]);
    var tm = s.match(/(\d{2}):(\d{2})/); if (tm) { out.h = +tm[1]; out.m = +tm[2]; }
    return out;
  }
  function fmt(kind, v) {
    var p = parse(v), parts = [];
    if (kind !== 'time' && p.d) parts.push(new Intl.DateTimeFormat(LANG, { day: 'numeric', month: 'long', year: 'numeric' }).format(p.d));
    if (kind !== 'date' && p.h !== null) parts.push(pad(p.h) + ':' + pad(p.m));
    return parts.join(', ');
  }
  var pop = null;
  function close() { if (pop) { pop.remove(); pop = null; document.removeEventListener('keydown', onKey); } }
  function onKey(e) { if (e.key === 'Escape') close(); }

  function column(max, step, cur, onPick) {
    var col = document.createElement('div'); col.className = 'dxp__col';
    var vals = []; for (var i = 0; i < max; i += step) vals.push(i);
    if (vals.indexOf(cur) === -1) { vals.push(cur); vals.sort(function (a, b) { return a - b; }); }
    vals.forEach(function (v) {
      var b = document.createElement('button'); b.type = 'button'; b.textContent = pad(v); b.dataset.v = v; if (v === cur) b.className = 'on';
      col.appendChild(b);
    });
    function mark(v) { col.querySelectorAll('button').forEach(function (b) { b.classList.toggle('on', +b.dataset.v === v); }); }
    col.addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; mark(+b.dataset.v); onPick(+b.dataset.v); b.scrollIntoView({ block: 'center', behavior: 'smooth' }); });
    var st = 0;
    col.addEventListener('scroll', function () {       // прокрутил колесом или пальцем — выбрано то, что в середине
      clearTimeout(st); st = setTimeout(function () {
        var mid = col.getBoundingClientRect().top + col.clientHeight / 2, best = null, dist = 1e9;
        col.querySelectorAll('button').forEach(function (b) { var r = b.getBoundingClientRect(), d = Math.abs(r.top + r.height / 2 - mid); if (d < dist) { dist = d; best = b; } });
        if (best && !best.classList.contains('on')) { mark(+best.dataset.v); onPick(+best.dataset.v); }
      }, 90);
    });
    setTimeout(function () { var on = col.querySelector('.on'); if (on) on.scrollIntoView({ block: 'center' }); }, 0);
    return col;
  }

  function show(input, kind, btn) {
    close();
    var cur = parse(VALUE.get.call(input)), now = new Date();
    var sel = cur.d ? new Date(cur.d) : null, view = new Date((sel || now).getFullYear(), (sel || now).getMonth(), 1);
    var h = cur.h !== null ? cur.h : (kind === 'date' ? 0 : now.getHours()), m = cur.m !== null ? cur.m : 0;
    var min = parse(input.min).d, max = parse(input.max).d;
    pop = document.createElement('div'); pop.className = 'dxp';
    var card = document.createElement('div'); card.className = 'dxp__c'; card.setAttribute('role', 'dialog'); pop.appendChild(card);
    function commit(done) {
      var v = '';
      if (kind === 'time') v = pad(h) + ':' + pad(m);
      else if (sel) v = iso(sel) + (kind === 'datetime-local' ? 'T' + pad(h) + ':' + pad(m) : '');
      input.value = v;
      input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
      if (done) { close(); btn.focus(); }
    }
    function draw() {
      card.innerHTML = '';
      if (kind !== 'time') {
        var top = document.createElement('div'); top.className = 'dxp__top';
        var name = document.createElement('b'); name.textContent = new Intl.DateTimeFormat(LANG, { month: 'long' }).format(view) + ' ' + view.getFullYear();
        var pv = document.createElement('button'); pv.type = 'button'; pv.className = 'dxp__nav'; pv.innerHTML = PREV; pv.setAttribute('aria-label', T('Предыдущий месяц'));
        var nx = document.createElement('button'); nx.type = 'button'; nx.className = 'dxp__nav'; nx.innerHTML = NEXT; nx.setAttribute('aria-label', T('Следующий месяц'));
        pv.addEventListener('click', function () { view = new Date(view.getFullYear(), view.getMonth() - 1, 1); draw(); });
        nx.addEventListener('click', function () { view = new Date(view.getFullYear(), view.getMonth() + 1, 1); draw(); });
        top.appendChild(name); top.appendChild(pv); top.appendChild(nx); card.appendChild(top);
        var wd = document.createElement('div'); wd.className = 'dxp__wd';
        for (var i = 0; i < 7; i++) { var s = document.createElement('span'); s.textContent = new Intl.DateTimeFormat(LANG, { weekday: 'short' }).format(new Date(2024, 0, 1 + i)); wd.appendChild(s); }   // 1 января 2024 — понедельник
        card.appendChild(wd);
        var grid = document.createElement('div'); grid.className = 'dxp__g';
        var first = new Date(view), shift = (first.getDay() + 6) % 7; first.setDate(1 - shift);
        for (var k = 0; k < 42; k++) {
          var d = new Date(first.getFullYear(), first.getMonth(), first.getDate() + k);
          var b = document.createElement('button'); b.type = 'button'; b.className = 'dxp__d'; b.textContent = d.getDate(); b.dataset.d = iso(d);
          if (d.getMonth() !== view.getMonth()) b.classList.add('is-out');
          if (iso(d) === iso(now)) b.classList.add('is-today');
          if (sel && iso(d) === iso(sel)) b.classList.add('on');
          if ((min && d < min) || (max && d > max)) b.disabled = true;
          grid.appendChild(b);
        }
        grid.addEventListener('click', function (e) {
          var b = e.target.closest('.dxp__d'); if (!b || b.disabled) return;
          var p = parse(b.dataset.d).d; sel = p; view = new Date(p.getFullYear(), p.getMonth(), 1);
          if (kind === 'date') commit(true); else draw();
        });
        card.appendChild(grid);
      }
      if (kind !== 'date') {
        var tm = document.createElement('div'); tm.className = 'dxp__time';
        tm.appendChild(column(24, 1, h, function (v) { h = v; }));
        var colon = document.createElement('i'); colon.textContent = ':'; tm.appendChild(colon);
        tm.appendChild(column(60, 5, m, function (v) { m = v; }));
        card.appendChild(tm);
      }
      var foot = document.createElement('div'); foot.className = 'dxp__foot';
      if (!input.required) { var clr = document.createElement('button'); clr.type = 'button'; clr.textContent = T('Очистить'); clr.addEventListener('click', function () { sel = null; input.value = ''; input.dispatchEvent(new Event('change', { bubbles: true })); close(); }); foot.appendChild(clr); }
      if (kind !== 'time') { var td = document.createElement('button'); td.type = 'button'; td.textContent = T('Сегодня'); td.addEventListener('click', function () { sel = new Date(now.getFullYear(), now.getMonth(), now.getDate()); view = new Date(sel.getFullYear(), sel.getMonth(), 1); if (kind === 'date') commit(true); else draw(); }); foot.appendChild(td); }
      if (kind !== 'date') { var ok = document.createElement('button'); ok.type = 'button'; ok.className = 'is-main'; ok.textContent = T('Готово'); ok.addEventListener('click', function () { if (kind === 'datetime-local' && !sel) sel = new Date(now.getFullYear(), now.getMonth(), now.getDate()); commit(true); }); foot.appendChild(ok); }
      card.appendChild(foot);
    }
    draw();
    pop.addEventListener('click', function (e) { if (e.target === pop) close(); });
    document.addEventListener('keydown', onKey);
    document.body.appendChild(pop);
  }

  function enhance(input) {
    var kind = input.dataset.dx || input.getAttribute('type');
    if ('native' in input.dataset || ['date', 'datetime-local', 'time'].indexOf(kind) === -1) return;
    if (input.dataset.dx) {                              // уже оформлено… или это копия оформленного (cloneNode): у копии кнопка «мёртвая»
      var was = input.parentNode;
      if (!was || !was.classList.contains('dx') || was._dx) return;
      was.parentNode.insertBefore(input, was); was.remove();
    }
    input.dataset.dx = kind;
    var wrap = document.createElement('span'); wrap.className = 'dx'; wrap._dx = true;
    var btn = document.createElement('button'); btn.type = 'button'; btn.className = 'dx__btn'; btn.setAttribute('aria-haspopup', 'dialog');
    var lab = input.getAttribute('aria-label') || input.getAttribute('placeholder') || '';
    if (lab) btn.setAttribute('aria-label', lab);
    input.parentNode.insertBefore(wrap, input); wrap.appendChild(input); wrap.appendChild(btn);
    input.type = 'hidden';
    function label() {
      var text = fmt(kind, VALUE.get.call(input));
      btn.innerHTML = (kind === 'time' ? CLK : CAL) + '<span></span>';
      btn.querySelector('span').textContent = text || lab || (kind === 'time' ? T('Время') : T('Выбрать дату'));
      btn.classList.toggle('is-empty', !text);
    }
    // другие скрипты пишут в поле через input.value = … — подпись на кнопке должна обновляться
    Object.defineProperty(input, 'value', { configurable: true, get: function () { return VALUE.get.call(this); }, set: function (v) { VALUE.set.call(this, v); label(); } });
    btn.addEventListener('click', function () { show(input, kind, btn); });
    if (input.id) { var l = document.querySelector('label[for="' + input.id + '"]'); if (l) l.addEventListener('click', function (e) { e.preventDefault(); btn.focus(); }); }
    label();
  }
  function scan(root) { (root || document).querySelectorAll('input[type=date],input[type=datetime-local],input[type=time],input[data-dx]').forEach(enhance); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { scan(); }); else scan();
  new MutationObserver(function (list) { list.forEach(function (m) { m.addedNodes.forEach(function (n) { if (n.nodeType === 1) { if (n.tagName === 'INPUT') enhance(n); else if (n.querySelector) scan(n); } }); }); })
    .observe(document.documentElement, { childList: true, subtree: true });
})();
