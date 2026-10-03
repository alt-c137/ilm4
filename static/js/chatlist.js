/* ilm4 · список чатов «как в Telegram»: вкладки-папки без перезагрузки, архив, меню чата
   (закрепить, без звука, в архив, прочитано / не прочитано, в папку, очистить, удалить). */
(function () {
  'use strict';
  var side = document.getElementById('tg-side');
  if (!side) return;
  var list = document.getElementById('tg-list'), tabs = document.getElementById('tg-tabs');
  if (!list) return;                       // в сообществе слева не список чатов, а его каналы
  var q = document.getElementById('tg-q');
  var csrf = (side.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';
  var rows = Array.prototype.slice.call(list.querySelectorAll('.tgrow[data-id]'));
  var archRow = document.getElementById('tg-archive'), archBack = document.getElementById('tg-archive-back');
  var emptyFolder = document.getElementById('tg-folder-empty');
  var IC = {};
  try { IC = JSON.parse(document.getElementById('ui-icons').textContent); } catch (e) { /* без значков меню всё равно работает */ }
  function ids(el, name) {
    var set = {}, raw = (el && el.dataset[name]) || '';
    raw.split(',').forEach(function (v) { if (v) set[v] = 1; });
    return set;
  }
  function order(el) { return ((el && el.dataset.pins) || '').split(',').filter(Boolean); }

  /* ---------- вкладки ---------- */
  var KEY = 'ilm4.chatFolder';
  var current = side.dataset.folder || '';
  if (!/[?&]f=/.test(location.search)) {
    try { current = sessionStorage.getItem(KEY) || ''; } catch (e) { current = ''; }
  }
  function tabOf(key) { return tabs ? tabs.querySelector('.tgtab[data-f="' + key + '"]') : null; }
  if (current && current !== 'archive' && !tabOf(current)) current = '';
  if (current === 'archive' && !archRow) current = '';

  function apply() {
    var needle = q ? q.value.trim().toLowerCase() : '';
    var tab = current === 'archive' ? archRow : tabOf(current);
    var allow = ids(tab, 'ids'), pins = current && current !== 'archive' ? order(tab) : [];
    var shown = 0, frag = document.createDocumentFragment(), pinned = {};
    pins.forEach(function (id) { pinned[id] = 1; });
    // порядок: закреплённые в этой папке — первыми (в порядке закрепления), остальные — как пришли с сервера
    var sorted = rows.slice();
    if (pins.length) {
      sorted.sort(function (a, b) {
        var pa = pins.indexOf(a.dataset.id), pb = pins.indexOf(b.dataset.id);
        if (pa === -1 && pb === -1) return rows.indexOf(a) - rows.indexOf(b);
        if (pa === -1) return 1;
        if (pb === -1) return -1;
        return pa - pb;
      });
    }
    sorted.forEach(function (r) {
      var ok = needle ? r.dataset.q.indexOf(needle) !== -1 : !!allow[r.dataset.id];
      r.hidden = !ok;
      if (ok) shown++;
      var isPin = current && current !== 'archive' ? !!pinned[r.dataset.id] : r.dataset.pin === '1';
      r.classList.toggle('is-pinned', isPin && !needle);
      var mark = r.querySelector('.tgrow__pin');
      if (mark) mark.hidden = !isPin;
      else if (isPin && !r.querySelector('.tgrow__badge')) {
        r.querySelector('.tgrow__bot').insertAdjacentHTML('beforeend', '<span class="tgrow__pin">' + (IC.tack || '') + '</span>');
      }
      frag.appendChild(r);
    });
    if (emptyFolder) list.insertBefore(frag, emptyFolder); else list.appendChild(frag);
    if (archRow) archRow.hidden = !!current || !!needle;
    if (archBack) archBack.hidden = current !== 'archive' || !!needle;
    if (emptyFolder) emptyFolder.hidden = shown > 0 || !rows.length || !!needle || !current;
    if (tabs) tabs.querySelectorAll('.tgtab[data-f]').forEach(function (t) { t.classList.toggle('on', t.dataset.f === (current === 'archive' ? '' : current)); });
    var on = tabs && tabs.querySelector('.tgtab.on');
    if (on && on.scrollIntoView && tabs.scrollWidth > tabs.clientWidth) on.scrollIntoView({ block: 'nearest', inline: 'center' });
  }
  function go(key) {
    current = key;
    try { sessionStorage.setItem(KEY, key); } catch (e) { /* приватный режим */ }
    apply();
  }
  if (tabs) tabs.addEventListener('click', function (e) {
    var t = e.target.closest('.tgtab[data-f]');
    if (!t || e.metaKey || e.ctrlKey) return;
    e.preventDefault(); go(t.dataset.f);
  });
  if (archRow) archRow.addEventListener('click', function (e) { e.preventDefault(); go('archive'); });
  if (archBack) archBack.addEventListener('click', function (e) { e.preventDefault(); go(''); });
  if (q) q.addEventListener('input', apply);

  /* ---------- единый поиск (как в Telegram): под своими чатами — «Глобальный поиск» и «Сообщения» ---------- */
  var found = document.createElement('div'); found.id = 'tg-found'; found.hidden = true; list.parentNode.insertBefore(found, list.nextSibling);
  var findT = 0, findN = 0;
  function esc(x) { var d = document.createElement('div'); d.textContent = x == null ? '' : x; return d.innerHTML; }
  function face(p) { return p && p.url ? '<img class="tava" src="' + esc(p.url) + '" alt="" loading="lazy">' : '<span class="tava tava--h' + ((p && p.hue) || 0) + '">' + esc((p && p.letter) || '#') + '</span>'; }
  function rowHtml(r) {
    return '<a class="tgrow" href="' + esc(r.href) + '">' + (r.pic ? face(r.pic) : '<span class="tava tava--h2">' + (IC.search || '') + '</span>') +
      '<span class="tgrow__b"><span class="tgrow__top"><b>' + esc(r.name) + '</b>' + (r.time ? '<time>' + esc(r.time) + '</time>' : '') + '</span>' +
      '<span class="tgrow__bot"><span class="tgrow__msg">' + esc(r.sub) + '</span></span></span></a>';
  }
  function findRemote() {
    var text = q.value.trim(), n = ++findN;
    if (text.length < 2) { found.hidden = true; found.innerHTML = ''; return; }
    fetch('/chat/find/?q=' + encodeURIComponent(text), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (j) {
      if (n !== findN) return;
      var html = '';
      if (j.global && j.global.length) html += '<h3 class="tgfound__h">' + _t('Глобальный поиск') + '</h3>' + j.global.map(rowHtml).join('');
      if (j.messages && j.messages.length) html += '<h3 class="tgfound__h">' + _t('Сообщения') + '</h3>' + j.messages.map(rowHtml).join('');
      found.innerHTML = html; found.hidden = !html;
    }).catch(function () { /* нет сети — остаётся поиск по своим чатам */ });
  }
  if (q) q.addEventListener('input', function () { clearTimeout(findT); findT = setTimeout(findRemote, 280); });
  apply();

  /* ---------- меню ---------- */
  var menu = document.createElement('div');
  menu.className = 'ctxmenu'; menu.hidden = true; menu.setAttribute('role', 'menu');
  document.body.appendChild(menu);
  function item(key, icon, text, cls) {
    return '<button type="button" role="menuitem" data-a="' + key + '"' + (cls ? ' class="' + cls + '"' : '') + '>' + (IC[icon] || '') + '<span>' + text + '</span></button>';
  }
  function place(x, y) {
    menu.hidden = false;
    var w = menu.offsetWidth, h = menu.offsetHeight;
    menu.style.left = Math.max(8, Math.min(x, innerWidth - w - 8)) + 'px';
    menu.style.top = Math.max(8, Math.min(y, innerHeight - h - 8)) + 'px';
    menu.classList.remove('pop'); void menu.offsetWidth; menu.classList.add('pop');
  }
  function close() { menu.hidden = true; menu.innerHTML = ''; }
  function post(url, data) {
    var fd = new FormData();
    fd.append('csrfmiddlewaretoken', csrf);            // пустая форма без единого поля сервером не принимается
    Object.keys(data || {}).forEach(function (k) { fd.append(k, data[k]); });
    return fetch(url, { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'fetch' } })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || 'error'); return j; }); });
  }
  function toast(text) {
    var t = document.createElement('div'); t.className = 'tg__toast'; t.textContent = text;
    document.body.appendChild(t); setTimeout(function () { t.remove(); }, 3500);
  }
  function act(row, action, extra) {
    post('/chat/' + row.dataset.id + '/state/' + action + '/', extra || {})
      .then(function () {
        // удалили или убрали в архив открытый чат — уходим в список
        if ((action === 'hide') && row.classList.contains('on')) location.href = '/chat/'; else location.reload();
      })
      .catch(function (e) { toast(e.message === 'error' ? _t('Не удалось') : e.message); });
  }
  function folderId() { return current && current !== 'archive' ? current : ''; }

  function openRowMenu(row, x, y) {
    var d = row.dataset, fid = folderId(), tab = tabOf(fid);
    var pinnedHere = fid ? order(tab).indexOf(d.id) !== -1 : d.pin === '1';
    var html = '';
    html += item(pinnedHere ? 'unpin' : 'pin', pinnedHere ? 'untack' : 'tack', pinnedHere ? _t('Открепить') : _t('Закрепить'));
    if (d.saved !== '1') html += item(d.muted ? 'unmute' : 'mute', d.muted ? 'bell' : 'belloff', d.muted ? _t('Включить звук') : _t('Без звука'));
    html += item(d.unread ? 'read' : 'unread', d.unread ? 'checks' : 'unread', d.unread ? _t('Пометить прочитанным') : _t('Пометить непрочитанным'));
    html += item(d.arch ? 'unarchive' : 'archive', d.arch ? 'unarchive' : 'archive', d.arch ? _t('Вернуть из архива') : _t('В архив'));
    if (tabs && tabs.querySelector('.tgtab[data-f]:not([data-f=""])')) html += item('folders', 'folderplus', _t('Добавить в папку…'));
    if (fid && ids(tab, 'ids')[d.id]) html += item('folder_remove', 'folder', _t('Убрать из этой папки'));
    html += item('clear', 'broom', _t('Очистить историю'));
    if (d.room) html += '<a role="menuitem" class="bad" href="/chat/' + d.id + '/info/">' + (IC.exit || '') + '<span>' + (d.room === 'channel' ? _t('Отписаться…') : _t('Выйти из группы…')) + '</span></a>';
    else html += item('hide', 'trash', _t('Удалить чат'), 'bad');
    menu.innerHTML = html; menu._row = row;
    place(x, y);
  }
  function openFolderPick(row, x, y) {
    var html = '<div class="ctxmenu__h">' + _t('Добавить в папку') + '</div>';
    tabs.querySelectorAll('.tgtab[data-f]').forEach(function (t) {
      if (!t.dataset.f) return;
      var inside = !!ids(t, 'ids')[row.dataset.id];
      html += '<button type="button" role="menuitem" data-folder="' + t.dataset.f + '" data-on="' + (inside ? '1' : '') + '">' +
        (inside ? (IC.check || '') : (IC.folder || '')) + '<span></span></button>';
    });
    html += '<a role="menuitem" href="/chat/folders/new/">' + (IC.plus || '') + '<span>' + _t('Новая папка') + '</span></a>';
    menu.innerHTML = html; menu._row = row;
    var names = menu.querySelectorAll('[data-folder] span'), i = 0;
    tabs.querySelectorAll('.tgtab[data-f]').forEach(function (t) { if (t.dataset.f) names[i++].textContent = t.dataset.title || t.textContent.trim(); });
    place(x, y);
  }
  function openTabMenu(tab, x, y) {
    var all = '<a role="menuitem" href="/chat/folders/">' + (IC.sliders || '') + '<span>' + _t('Настроить папки') + '</span></a>';
    menu.innerHTML = tab.dataset.f ? '<a role="menuitem" href="/chat/folders/' + tab.dataset.f + '/">' + (IC.edit || '') + '<span>' + _t('Изменить папку') + '</span></a>' +
      all + item('folder_delete', 'trash', _t('Удалить папку'), 'bad') : all;
    menu._tab = tab; menu._row = null;
    place(x, y);
  }
  var pos = { x: 0, y: 0 };
  menu.addEventListener('click', function (e) {
    var b = e.target.closest('[data-a],[data-folder]'); if (!b) return;
    var row = menu._row, a = b.dataset.a, x = pos.x, y = pos.y;
    if (b.dataset.folder) { close(); act(row, b.dataset.on ? 'folder_remove' : 'folder_add', { folder: b.dataset.folder }); return; }
    if (a === 'folders') { openFolderPick(row, x, y); return; }
    var tab = menu._tab;
    close();
    if (a === 'folder_delete') {
      if (!confirm(_t('Удалить папку? Сами чаты останутся.'))) return;
      post('/chat/folders/', { what: 'delete', id: tab.dataset.f }).catch(function () {}).then(function () {
        try { sessionStorage.removeItem(KEY); } catch (err) { /* не страшно */ }
        location.href = '/chat/';
      });
      return;
    }
    if (a === 'clear' && !confirm(_t('Очистить историю? Сообщения пропадут только у вас.'))) return;
    if (a === 'hide' && !confirm(_t('Удалить чат? Он пропадёт из вашего списка; у собеседника переписка останется.'))) return;
    var extra = {};
    if ((a === 'pin' || a === 'unpin' || a === 'folder_remove') && folderId()) extra.folder = folderId();
    act(row, a, extra);
  });
  document.addEventListener('click', function (e) { if (!menu.hidden && !e.target.closest('.ctxmenu')) close(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  window.addEventListener('scroll', close, true);

  function target(e) {
    var row = e.target.closest('.tgrow[data-id]'); if (row) return { row: row };
    var tab = e.target.closest('.tgtab[data-f]'); if (tab) return { tab: tab };
    return null;
  }
  side.addEventListener('contextmenu', function (e) {
    var t = target(e); if (!t) return;
    e.preventDefault(); pos = { x: e.clientX, y: e.clientY };
    if (t.row) openRowMenu(t.row, pos.x, pos.y); else openTabMenu(t.tab, pos.x, pos.y);
  });
  // долгое нажатие на телефоне
  var lp = null, fired = false;
  side.addEventListener('pointerdown', function (e) {
    if (e.pointerType === 'mouse') return;
    var t = target(e); if (!t) return;
    fired = false; pos = { x: e.clientX, y: e.clientY };
    lp = setTimeout(function () {
      fired = true;
      if (navigator.vibrate) navigator.vibrate(12);
      if (t.row) openRowMenu(t.row, pos.x, pos.y); else openTabMenu(t.tab, pos.x, pos.y);
    }, 480);
  });
  side.addEventListener('pointermove', function (e) { if (Math.abs(e.clientX - pos.x) + Math.abs(e.clientY - pos.y) > 12) clearTimeout(lp); });
  ['pointerup', 'pointercancel'].forEach(function (ev) { side.addEventListener(ev, function () { clearTimeout(lp); }); });
  side.addEventListener('click', function (e) { if (fired) { e.preventDefault(); e.stopPropagation(); fired = false; } }, true);
})();
