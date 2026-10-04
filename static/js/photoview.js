/* ilm4 · просмотр фото на весь экран — как в Telegram: листание (свайп, стрелки), счётчик «2 из 5»,
   масштаб двойным нажатием, скачать; у своих фото профиля — «Сделать главным» и «Удалить».
   window.ilm4Photos(список [{url, id?, date?, name?}], с какого начать, {mine, csrf, onChange}) */
(function () {
  'use strict';
  var box = null, st = null;
  function T(s) { return window._t ? window._t(s) : s; }
  var X = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>';
  var L = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>';
  var R = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5l7 7-7 7"/></svg>';
  var D = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11M7.5 11 12 15.5 16.5 11M5 19.5h14"/></svg>';

  function build() {
    box = document.createElement('div');
    box.className = 'pview'; box.hidden = true; box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true');
    box.innerHTML = '<div class="pview__top"><button type="button" class="pview__b" data-p="close" aria-label="' + T('Закрыть') + '">' + X + '</button>' +
      '<div class="pview__cap"><b></b><span></span></div><a class="pview__b" data-p="save" download aria-label="' + T('Скачать') + '">' + D + '</a></div>' +
      '<div class="pview__stage"><button type="button" class="pview__nav pview__nav--l" data-p="prev" aria-label="' + T('Назад') + '">' + L + '</button>' +
      '<img alt="" draggable="false"><button type="button" class="pview__nav pview__nav--r" data-p="next" aria-label="' + T('Вперёд') + '">' + R + '</button></div>' +
      '<div class="pview__dots"></div><div class="pview__acts"></div>';
    document.body.appendChild(box);
    box.addEventListener('click', function (e) {
      var b = e.target.closest('[data-p]');
      if (!b) { if (e.target.classList.contains('pview__stage')) close(); return; }
      var p = b.dataset.p;
      if (p === 'close') close();
      else if (p === 'prev') go(-1);
      else if (p === 'next') go(1);
      else if (p === 'main' || p === 'delete') act(p);
      else if (p === 'add' && st.opts.onAdd) { close(); st.opts.onAdd(); }
    });
    var img = box.querySelector('img'), x0 = null, y0 = null, moved = 0;
    img.addEventListener('dblclick', function () { img.classList.toggle('is-zoom'); });
    box.addEventListener('touchstart', function (e) { if (e.touches.length === 1) { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; moved = 0; } }, { passive: true });
    box.addEventListener('touchmove', function (e) {
      if (x0 === null || img.classList.contains('is-zoom')) return;
      moved = e.touches[0].clientX - x0;
      var dy = e.touches[0].clientY - y0;
      if (Math.abs(dy) > Math.abs(moved) && Math.abs(dy) > 12) { img.style.transform = 'translateY(' + dy + 'px) scale(' + Math.max(.7, 1 - Math.abs(dy) / 900) + ')'; moved = 0; box.dataset.dy = dy; }
      else img.style.transform = 'translateX(' + moved + 'px)';
    }, { passive: true });
    box.addEventListener('touchend', function () {
      var dy = +box.dataset.dy || 0; delete box.dataset.dy;
      img.style.transform = '';
      if (Math.abs(dy) > 110) close();                       // смахнул вверх или вниз — закрыть
      else if (moved > 60) go(-1); else if (moved < -60) go(1);
      x0 = null; moved = 0;
    });
    document.addEventListener('keydown', function (e) {
      if (!st) return;
      if (e.key === 'Escape') close(); else if (e.key === 'ArrowLeft') go(-1); else if (e.key === 'ArrowRight') go(1);
    });
  }
  function draw() {
    var p = st.list[st.i], img = box.querySelector('img');
    img.classList.remove('is-zoom'); img.src = p.url;
    box.querySelector('.pview__cap b').textContent = p.name || '';
    box.querySelector('.pview__cap span').textContent = (st.list.length > 1 ? (st.i + 1) + ' ' + T('из') + ' ' + st.list.length : '') + (p.date ? (st.list.length > 1 ? ' · ' : '') + p.date : '');
    box.querySelector('[data-p="save"]').href = p.url;
    box.querySelector('.pview__nav--l').hidden = st.i === 0;
    box.querySelector('.pview__nav--r').hidden = st.i === st.list.length - 1;
    var dots = box.querySelector('.pview__dots');
    dots.innerHTML = st.list.length > 1 && st.list.length <= 30 ? st.list.map(function (_x, i) { return '<i' + (i === st.i ? ' class="on"' : '') + '></i>'; }).join('') : '';
    var acts = '';
    if (st.opts.mine) {
      if (st.i > 0) acts += '<button type="button" data-p="main">' + T('Сделать главным') + '</button>';
      if (st.opts.onAdd) acts += '<button type="button" data-p="add">' + T('Новое фото') + '</button>';
      acts += '<button type="button" data-p="delete" class="bad">' + T('Удалить') + '</button>';
    }
    box.querySelector('.pview__acts').innerHTML = acts;
  }
  function go(by) {
    var n = st.i + by;
    if (n < 0 || n >= st.list.length) return;
    st.i = n; draw();
  }
  function close() { if (!box) return; box.hidden = true; st = null; document.documentElement.classList.remove('pview-open'); }
  function act(what) {
    var p = st.list[st.i];
    if (what === 'delete' && !confirm(T('Удалить это фото?'))) return;
    var fd = new FormData(); fd.append(what, p.id); fd.append('csrfmiddlewaretoken', st.opts.csrf || '');
    fetch(st.opts.url || '/accounts/photos/', { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-CSRFToken': st.opts.csrf || '' } })
      .then(function (r) { return r.json(); }).then(function () { location.reload(); }).catch(function () { close(); });
  }
  window.ilm4Photos = function (list, index, opts) {
    if (!list || !list.length) return;
    if (!box) build();
    st = { list: list, i: Math.max(0, Math.min(index || 0, list.length - 1)), opts: opts || {} };
    draw(); box.hidden = false; document.documentElement.classList.add('pview-open');
  };

  // страницы профиля и сведений о группе: нажал на аватар — открылись фото
  document.addEventListener('click', function (e) {
    var a = e.target.closest('[data-photos]'); if (!a) return;
    var src = document.getElementById(a.dataset.photos), list = [];
    try { list = JSON.parse(src.textContent) || []; } catch (err) { list = []; }
    if (!list.length) return;
    e.preventDefault();
    var csrf = (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';
    var picker = a.dataset.picker && document.getElementById(a.dataset.picker);
    window.ilm4Photos(list, 0, { mine: a.dataset.mine === '1', csrf: csrf, onAdd: picker ? function () { if (window.ilm4PhotoSource) window.ilm4PhotoSource(picker); else picker.click(); } : null });
  });
})();
