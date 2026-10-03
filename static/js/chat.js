/* ilm4 · мессенджер: сообщения, фото, голосовые, видеокружки, звонки (WebRTC).
   Сервер — только ретранслятор сигналов звонка; голос и видео идут напрямую
   между браузерами. Каждая функция включается/выключается в админке (cfg.features). */
(function () {
  'use strict';
  var cfg = JSON.parse(document.getElementById('chat-cfg').textContent);
  var F = cfg.features || {};
  var log = document.getElementById('chat-log');
  var form = document.getElementById('chat-form');
  var input = document.getElementById('chat-body');
  var csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
  var seen = {};
  log.querySelectorAll('[data-id]').forEach(function (el) { seen[el.dataset.id] = 1; });

  /* ---------- утилиты ---------- */
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML.replace(/\n/g, '<br>'); }
  function mmss(s) { s = Math.max(0, Math.round(s || 0)); return Math.floor(s / 60) + ':' + ('0' + s % 60).slice(-2); }
  function fsize(n) {
    n = n || 0;
    if (n < 1024) return n + ' ' + _t('Б');
    if (n < 1048576) return Math.round(n / 1024) + ' ' + _t('КБ');
    if (n < 1073741824) return (n / 1048576).toFixed(1).replace('.0', '') + ' ' + _t('МБ');
    return (n / 1073741824).toFixed(2).replace(/\.?0+$/, '') + ' ' + _t('ГБ');
  }
  function toBottom() { log.scrollTop = log.scrollHeight; }
  function toast(text) {
    var t = document.createElement('div'); t.className = 'tg__toast'; t.textContent = text;
    document.body.appendChild(t); setTimeout(function () { t.remove(); }, 3500);
  }
  var ICON = {
    play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M8 5.5v13l11-6.5z"/></svg>',
    pause: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M9 5.5v13M15 5.5v13"/></svg>',
    clip: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11.5l-8.2 8.2a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7l-8.5 8.5a1.7 1.7 0 0 1-2.4-2.4l7.8-7.8"/></svg>',
    shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 5 6v5c0 4.5 3 8.3 7 10 4-1.7 7-5.5 7-10V6z"/><path d="M12 8v4.5M12 16h.01"/></svg>',
    clock: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
    eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/></svg>',
    call: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 3.5h3l1.5 4-2 1.5a12 12 0 0 0 6 6l1.5-2 4 1.5v3a2 2 0 0 1-2.2 2A16.5 16.5 0 0 1 4.5 5.7 2 2 0 0 1 6.5 3.5z"/></svg>'
  };

  var IC = {};
  try { IC = JSON.parse(document.getElementById('ui-icons').textContent); } catch (e) { /* значки меню необязательны */ }
  var PINS = [];
  try { PINS = JSON.parse(document.getElementById('chat-pins').textContent) || []; } catch (e) { PINS = []; }

  /* ---------- вывод сообщений ---------- */
  function lastDay() { var d = log.querySelectorAll('.tg__day'); return d.length ? d[d.length - 1].dataset.day : ''; }
  function rxHTML(list, my) {
    return (list || []).map(function (r) {
      return '<button type="button" class="rx' + (r.e === my ? ' rx--me' : '') + '" data-e="' + esc(r.e) + '">' + esc(r.e) + '<i>' + r.n + '</i></button>';
    }).join('');
  }
  function fwdHTML(f) {
    if (!f) return '';
    var who = f.user ? '<a href="/accounts/u/' + f.user + '/">' + esc(f.name) + '</a>'
      : f.room ? '<a href="/chat/' + f.room + '/">' + esc(f.name) + '</a>' : '<b>' + esc(f.name) + '</b>';
    return '<span class="bub__fwd">' + (IC.forward || '') + _t('Переслано от') + ' ' + who + '</span>';
  }
  function replyHTML(r) {
    if (!r) return '';
    return '<button type="button" class="bub__reply bub__reply--h' + (r.hue || 0) + '" data-goto="' + r.id + '"><b>' + esc(r.name) + '</b><span>' + esc(r.text) + '</span></button>';
  }
  function metaHTML(d, mine) {
    var views = d.room === 'channel' && !d.scheduled ? '<span class="bub__views">' + ICON.eye + (d.views || 0) + '</span>' : '';
    return (d.pinned ? '<span class="bub__pin">' + (IC.tack || '') + '</span>' : '') + views +
      (d.edited ? '<span class="bub__ed">' + _t('изменено') + '</span>' : '') +
      (d.scheduled ? '' : esc(d.time || '')) + (mine && !d.scheduled && d.room !== 'channel' ? '<span class="tick' + (d.read ? ' tick--2' : '') + '"></span>' : '');
  }
  function msgHTML(d, mine) {
    if (d.kind === 'system') return '<div class="tg__sys" data-id="' + d.id + '"><span>' + esc(d.body) + ' · ' + esc(d.time) + '</span></div>';
    var media = '';
    if (d.kind === 'photo') media = '<a class="bub__photo" href="' + d.url + '" target="_blank" rel="noopener"><img src="' + d.url + '" alt="' + _t('Фото') + '"' + (d.w ? ' width="' + d.w + '" height="' + d.h + '"' : '') + '></a>';
    if (d.kind === 'voice') media = '<div class="voice" data-src="' + d.url + '"><button type="button" class="voice__play" aria-label="' + _t('Слушать') + '">' + ICON.play + '</button><span class="voice__bar"><i></i></span><span class="voice__t">' + mmss(d.duration) + '</span><button type="button" class="voice__sp" aria-label="' + _t('Скорость') + '">1×</button></div>';
    if (d.kind === 'video') media = '<div class="bub__video"><video src="' + d.url + '" controls preload="metadata" playsinline></video></div>';
    if (d.kind === 'file') media = '<a class="bub__file" href="' + d.url + '" download><span class="bub__fileico">' + ICON.clip + '</span><span class="bub__fileb"><b>' + esc(d.file_name || _t('Файл')) + '</b><small>' + fsize(d.file_size) + '</small></span></a>' +
      (d.file_risky && !mine ? '<span class="bub__risk">' + ICON.shield + _t('Это программа. Открывайте, только если доверяете отправителю.') + '</span>' : '');
    if (d.kind === 'circle') media = '<div class="circle" data-src="' + d.url + '"><video src="' + d.url + '" preload="metadata" playsinline></video><span class="circle__t">' + mmss(d.duration) + '</span><span class="circle__play">' + ICON.play + '</span></div>';
    var sched = d.scheduled ? '<span class="bub__sched">' + ICON.clock + _t('отправится') + ' ' + esc(d.scheduled_label) + '</span>' +
      '<span class="bub__schedact"><button type="button" data-sched-act="send">' + _t('Отправить сейчас') + '</button>' +
      '<button type="button" data-sched-act="cancel">' + _t('Удалить') + '</button></span>' : '';
    var who = (d.room === 'group' && !mine && lastSender !== d.sender_id)
      ? '<span class="bub__who bub__who--h' + (d.hue || 0) + '">' + esc(d.sender_name) + '</span>' : '';
    var comments = cfg.comments && !d.scheduled ? '<a class="bub__comments" href="/chat/' + cfg.thread + '/post/' + d.id + '/">' + (IC.comment || '') +
      '<span>' + (d.comments ? _t('Комментарии') + ' · ' + d.comments : _t('Комментировать')) + '</span></a>' : '';
    return '<div class="bub bub--in bub--' + d.kind + (mine ? ' bub--me' : '') + (d.scheduled ? ' bub--sched' : '') + (d.pinned ? ' is-pinned' : '') +
      ' bub--tail" data-id="' + d.id + '" data-kind="' + d.kind + '" data-name="' + esc(d.sender_name) + '" data-ts="' + Math.floor(new Date(d.iso || Date.now()).getTime() / 1000) + '"' +
      (d.my_reaction ? ' data-my="' + esc(d.my_reaction) + '"' : '') + '>' + who + fwdHTML(d.fwd) + replyHTML(d.reply) + media +
      (d.body ? '<span class="bub__t">' + rich(d.body) + '</span>' : '') + sched +
      '<span class="bub__meta">' + metaHTML(d, mine) + '</span><span class="bub__rx">' + rxHTML(d.reactions, d.my_reaction) + '</span>' + comments + '</div>';
  }
  /* оформление текста, как в Telegram: **жирный**, __курсив__, ~~зачёркнутый~~, `код`, ||скрытый||, ссылки.
     Тот же разбор — на сервере (apps/chat/richtext.py): сначала экранируем, потом расставляем свои теги. */
  function rich(text) {
    var codes = [], out = esc(text);
    out = out.replace(/`([^`\n]+)`/g, function (_m, c) { codes.push(c); return '\u0000' + (codes.length - 1) + '\u0000'; });
    out = out.replace(/\*\*(?=\S)([\s\S]+?)\*\*/g, '<b>$1</b>').replace(/__(?=\S)([\s\S]+?)__/g, '<i>$1</i>')
      .replace(/~~(?=\S)([\s\S]+?)~~/g, '<s>$1</s>')
      .replace(/\|\|(?=\S)([\s\S]+?)\|\|/g, '<span class="spoiler" role="button" tabindex="0">$1</span>')
      .replace(/(^|[\s(])(https?:\/\/[^\s<]+[^\s<.,:;!?)\]»"'])/g, '$1<a href="$2" target="_blank" rel="noopener nofollow ugc">$2</a>');
    out = out.replace(/(<a [^>]*>[\s\S]*?<\/a>)|(^|[^\w@\/.])@([A-Za-z][A-Za-z0-9_]{3,31})(?![\w.])/g, function (m, link, pre, name) {
      return link || pre + '<a class="mention" href="/@' + name.toLowerCase() + '/">@' + name + '</a>';
    });
    out = out.replace(/\u0000(\d+)\u0000/g, function (_m, i) { return '<code>' + codes[+i] + '</code>'; });
    return out.replace(/\n/g, '<br>');
  }
  // скрытый текст открывается по нажатию
  log.addEventListener('click', function (e) { var sp = e.target.closest('.spoiler'); if (sp) sp.classList.add('is-open'); });

  var lastSender = null;      // чьё сообщение было последним — чтобы не повторять имя в группе
  function add(d) {
    if (d.comment_of) {                       // комментарий к посту канала — в ленту не идёт, только счётчик
      var cm = log.querySelector('.bub[data-id="' + d.comment_of + '"] .bub__comments span');
      if (cm) { var n = (parseInt((cm.textContent.match(/\d+/) || ['0'])[0], 10) || 0) + 1; cm.textContent = _t('Комментарии') + ' · ' + n; }
      return;
    }
    if (seen[d.id]) {
      // запланированное ушло (или «отправить сейчас») — убираем черновик и показываем как обычное
      var old = log.querySelector('.bub--sched[data-id="' + d.id + '"]');
      if (!old || d.scheduled) return;
      old.remove();
    }
    seen[d.id] = 1;
    var em = document.getElementById('chat-empty'); if (em) em.remove();
    if (d.day && d.day !== lastDay()) {
      var day = document.createElement('div'); day.className = 'tg__day'; day.dataset.day = d.day;
      day.innerHTML = '<span>' + _t('Сегодня') + '</span>'; log.appendChild(day);
    }
    var mine = d.sender_id === cfg.me;
    var prev = log.lastElementChild;
    if (prev && prev.classList.contains('bub') && prev.classList.contains('bub--me') === mine) prev.classList.remove('bub--tail');
    log.insertAdjacentHTML('beforeend', msgHTML(d, mine));
    lastSender = d.kind === 'system' ? null : d.sender_id;
    if (d.warn && !mine && cfg.warn_text) {        // просят предоплату — предупреждаем получателя
      log.insertAdjacentHTML('beforeend', '<div class="tg__warn bub--in">' + ICON.shield + esc(cfg.warn_text) + '</div>');
    }
    if (mine || nearBottom()) toBottom(); else bumpFresh();
    if (!mine) stopTyping(d.sender_id);
  }

  /* ---------- прокрутка: кнопка «вниз» со счётчиком новых ---------- */
  var downBtn = document.getElementById('to-bottom'), downN = document.getElementById('to-bottom-n'), fresh = 0;
  function nearBottom() { return log.scrollHeight - log.scrollTop - log.clientHeight < 160; }
  function bumpFresh() { fresh++; if (downN) { downN.textContent = fresh; downN.hidden = false; } if (downBtn) downBtn.hidden = false; }
  log.addEventListener('scroll', function () {
    var far = log.scrollHeight - log.scrollTop - log.clientHeight > 420;
    if (downBtn) downBtn.hidden = !far && !fresh;
    if (!far && fresh) { fresh = 0; if (downN) downN.hidden = true; if (downBtn) downBtn.hidden = true; }
  });
  if (downBtn) downBtn.addEventListener('click', function () {
    if (cfg.at) { location.href = location.pathname; return; }
    log.scrollTo({ top: log.scrollHeight, behavior: 'smooth' }); fresh = 0; downN.hidden = true;
  });

  /* ---------- запросы ---------- */
  function post(url, data) {
    var fd = new FormData();
    fd.append('csrfmiddlewaretoken', csrf);            // пустая форма без единого поля сервером не принимается
    Object.keys(data || {}).forEach(function (k) {
      if (Array.isArray(data[k])) data[k].forEach(function (v) { fd.append(k, v); }); else fd.append(k, data[k]);
    });
    return fetch(url, { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'fetch' } })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) { var err = new Error(j.error || _t('Не удалось')); throw err; } return j; }); });
  }
  function fail(e) { toast(e && e.message && e.message !== 'Failed to fetch' ? e.message : _t('Нет соединения — попробуйте ещё раз')); }
  function bubOf(id) { return log.querySelector('.bub[data-id="' + id + '"]'); }
  function snippet(bub) {
    var t = bub.querySelector('.bub__t');
    if (t) return t.innerText.replace(/\s+/g, ' ').slice(0, 120);
    return { photo: _t('Фото'), video: _t('Видео'), voice: _t('Голосовое сообщение'), circle: _t('Видеосообщение'), file: _t('Файл') }[bub.dataset.kind] || '';
  }

  /* ---------- переход к сообщению (ответ, закреп, поиск) ---------- */
  function jump(id) {
    var el = log.querySelector('[data-id="' + id + '"]');
    if (!el) { location.href = location.pathname + '?at=' + id; return; }
    el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    el.classList.remove('is-flash'); void el.offsetWidth; el.classList.add('is-flash');
  }
  log.addEventListener('click', function (e) {
    var r = e.target.closest('[data-goto]'); if (r) { e.preventDefault(); jump(r.dataset.goto); }
  });

  /* ---------- фото: просмотр на весь экран, листаются все фото переписки ---------- */
  log.addEventListener('click', function (e) {
    var a = e.target.closest('.bub__photo'); if (!a || !window.ilm4Photos || e.metaKey || e.ctrlKey) return;
    e.preventDefault();
    var all = Array.prototype.slice.call(log.querySelectorAll('.bub__photo'));
    window.ilm4Photos(all.map(function (x) {
      var bub = x.closest('.bub'), meta = bub && bub.querySelector('.bub__meta');
      return { url: x.getAttribute('href'), name: bub ? bub.dataset.name : '', date: meta ? meta.textContent.trim() : '' };
    }), all.indexOf(a), {});
  });

  /* ---------- удалить сообщение из ленты ---------- */
  function removeMsg(id) {
    var el = log.querySelector('[data-id="' + id + '"]'); if (!el) return;
    var w = log.querySelector('[data-warn="' + id + '"]'); if (w) w.remove();
    el.classList.add('bub--gone'); setTimeout(function () { el.remove(); }, 180);
    delete seen[id];
    PINS = PINS.filter(function (p) { return String(p.id) !== String(id); }); drawPin();
    if (replyTo && String(replyTo.id) === String(id)) clearReply();
  }

  /* ---------- ответ и правка: полоска над полем ввода ---------- */
  var replyBar = document.getElementById('reply-bar'), replyName = document.getElementById('reply-name');
  var replyText = document.getElementById('reply-text'), replyIc = document.getElementById('reply-ic');
  var replyTo = null, editing = null;
  function showBar(icon, title, text) {
    if (!replyBar) return;
    replyIc.innerHTML = IC[icon] || ''; replyName.textContent = title; replyText.textContent = text; replyBar.hidden = false;
  }
  function clearReply() {
    replyTo = null;
    if (editing) { editing = null; input.value = ''; grow(); syncButtons(); }
    if (replyBar) replyBar.hidden = true;
  }
  function startReply(bub) {
    if (!cfg.can_post || bub.classList.contains('bub--sched')) return;
    if (editing) { editing = null; input.value = ''; }
    replyTo = { id: bub.dataset.id };
    showBar('reply', bub.dataset.name || '', snippet(bub));
    input.focus();
  }
  function startEdit(bub) {
    var t = bub.querySelector('.bub__t');
    replyTo = null; editing = { id: bub.dataset.id };
    showBar('edit', _t('Изменение сообщения'), snippet(bub));
    input.value = t ? t.innerText : ''; grow(); syncButtons(); input.focus();
    // в ленте текст уже оформлен — исходный (со знаками **жирный**, ||скрытый||) берём с сервера
    post('/chat/msg/' + bub.dataset.id + '/raw/').then(function (j) {
      if (editing && editing.id === bub.dataset.id) { input.value = j.body || ''; grow(); syncButtons(); }
    }).catch(function () {});
  }
  if (replyBar) document.getElementById('reply-x').addEventListener('click', clearReply);
  log.addEventListener('dblclick', function (e) {            // двойной щелчок — ответить (как в Telegram на компьютере)
    var bub = e.target.closest('.bub[data-id]'); if (!bub || e.target.closest('a,video,button,.voice,.circle')) return;
    var sel = window.getSelection && window.getSelection(); if (sel) sel.removeAllRanges();
    startReply(bub);
  });
  function applyEdit(d) {
    var bub = bubOf(d.id); if (!bub) return;
    var t = bub.querySelector('.bub__t');
    if (d.body) {
      if (!t) { t = document.createElement('span'); t.className = 'bub__t'; bub.insertBefore(t, bub.querySelector('.bub__meta')); }
      t.innerHTML = rich(d.body);
    } else if (t) t.remove();
    bub._raw = d.body;
    var meta = bub.querySelector('.bub__meta');
    if (meta && !bub.classList.contains('bub--sched')) {
      var read = !!meta.querySelector('.tick--2');
      meta.innerHTML = metaHTML({ pinned: bub.classList.contains('is-pinned'), room: cfg.room, views: (meta.querySelector('.bub__views') || {}).textContent, edited: d.edited, time: d.time, read: read }, bub.classList.contains('bub--me'));
    }
    PINS.forEach(function (p) { if (p.id === d.id) p.body = d.body; }); drawPin();
  }

  /* ---------- реакции ---------- */
  function applyReaction(d) {
    var bub = bubOf(d.id); if (!bub) return;
    if (d.user_id === cfg.me) { if (d.emoji) bub.dataset.my = d.emoji; else delete bub.dataset.my; }
    var box = bub.querySelector('.bub__rx');
    if (box) box.innerHTML = rxHTML(d.reactions, bub.dataset.my || '');
  }
  function react(id, emoji) {
    post('/chat/msg/' + id + '/react/', { emoji: emoji })
      .then(function (j) { applyReaction({ id: j.id, reactions: j.reactions, user_id: cfg.me, emoji: j.my_reaction }); }).catch(fail);
  }
  log.addEventListener('click', function (e) {
    var b = e.target.closest('.rx'); if (!b) return;
    react(b.closest('.bub').dataset.id, b.dataset.e);
  });

  /* ---------- закреплённые сообщения: полоска под шапкой ---------- */
  var pinBar = document.getElementById('pin-bar'), pinAt = -1;
  function pinText(p) {
    return p.body ? p.body.replace(/\*\*|__|~~|`|\|\|/g, '').slice(0, 90)
      : ({ photo: _t('Фото'), video: _t('Видео'), voice: _t('Голосовое сообщение'), circle: _t('Видеосообщение'), file: p.file_name || _t('Файл') }[p.kind] || '');
  }
  function drawPin() {
    if (!pinBar) return;
    if (!PINS.length) { pinBar.hidden = true; return; }
    if (pinAt < 0 || pinAt >= PINS.length) pinAt = PINS.length - 1;
    var p = PINS[pinAt];
    document.getElementById('pin-h').textContent = PINS.length > 1 ? _t('Закреплённое сообщение') + ' · ' + (pinAt + 1) + '/' + PINS.length : _t('Закреплённое сообщение');
    document.getElementById('pin-t').textContent = pinText(p);
    document.getElementById('pin-x').hidden = !cfg.can_pin;
    pinBar.hidden = false;
  }
  if (pinBar) {
    document.getElementById('pin-go').addEventListener('click', function () {
      if (!PINS.length) return;
      var id = PINS[pinAt].id;
      pinAt = pinAt > 0 ? pinAt - 1 : PINS.length - 1;       // следующее нажатие — предыдущий закреп
      jump(id); drawPin();
    });
    document.getElementById('pin-x').addEventListener('click', function () {
      var p = PINS[pinAt]; if (!p || !confirm(_t('Открепить сообщение?'))) return;
      post('/chat/msg/' + p.id + '/unpin/').catch(fail);
    });
    drawPin();
  }
  function applyPin(d) {
    PINS = PINS.filter(function (p) { return p.id !== d.id; });
    if (d.on && d.msg) { PINS.push(d.msg); PINS.sort(function (a, b) { return a.id - b.id; }); pinAt = PINS.length - 1; }
    var bub = bubOf(d.id);
    if (bub) {
      bub.classList.toggle('is-pinned', !!d.on);
      var meta = bub.querySelector('.bub__meta'), mark = meta && meta.querySelector('.bub__pin');
      if (d.on && meta && !mark) meta.insertAdjacentHTML('afterbegin', '<span class="bub__pin">' + (IC.tack || '') + '</span>');
      if (!d.on && mark) mark.remove();
    }
    drawPin();
  }

  /* ---------- «печатает…» ---------- */
  var sub = document.getElementById('tg-sub'), subHTML = sub ? sub.innerHTML : '', typers = {}, typingSent = 0;
  function drawTyping() {
    if (!sub) return;
    var names = Object.keys(typers).map(function (k) { return typers[k].name; });
    if (!names.length) { sub.innerHTML = subHTML; sub.classList.remove('is-typing'); return; }
    var what = typers[Object.keys(typers)[0]].what;
    var verb = what === 'voice' ? _t('записывает голосовое') : what === 'circle' ? _t('записывает кружок') : _t('печатает');
    sub.textContent = (cfg.room ? names.slice(0, 2).join(', ') + ' ' : '') + verb + '…';
    sub.classList.add('is-typing');
  }
  function stopTyping(uid) { if (typers[uid]) { clearTimeout(typers[uid].t); delete typers[uid]; drawTyping(); } }
  function onTyping(d) {
    stopTyping(d.user_id);
    typers[d.user_id] = { name: d.name, what: d.what, t: setTimeout(function () { stopTyping(d.user_id); }, 5500) };
    drawTyping();
  }
  function sayTyping(what) {
    if (cfg.room === 'channel' || !cfg.can_post) return;
    var now = Date.now(); if (now - typingSent < 4000) return;
    typingSent = now; wsSend({ type: 'typing', what: what || 'text' });
  }

  /* ---------- меню сообщения: реакции, ответить, изменить, копировать, переслать, закрепить, удалить ---------- */
  var msgMenu = document.createElement('div');
  msgMenu.className = 'ctxmenu msgmenu'; msgMenu.hidden = true; msgMenu.setAttribute('role', 'menu');
  document.body.appendChild(msgMenu);
  function mi(key, icon, text, cls) {
    return '<button type="button" role="menuitem" data-m="' + key + '"' + (cls ? ' class="' + cls + '"' : '') + '>' + (IC[icon] || '') + '<span>' + text + '</span></button>';
  }
  function openMsgMenu(bub, x, y) {
    var mine = bub.classList.contains('bub--me'), txt = bub.querySelector('.bub__t'), sched = bub.classList.contains('bub--sched');
    var kind = bub.dataset.kind, age = Date.now() / 1000 - (+bub.dataset.ts || 0);
    var html = '';
    if (!sched && cfg.reactions && cfg.reactions.length && cfg.member) {
      html += '<div class="ctxmenu__rx">' + cfg.reactions.map(function (e) {
        return '<button type="button" data-rx="' + e + '"' + (bub.dataset.my === e ? ' class="on"' : '') + '>' + e + '</button>';
      }).join('') + '</div>';
    }
    if (!sched && cfg.can_post) html += mi('reply', 'reply', _t('Ответить'));
    if (mine && kind !== 'voice' && kind !== 'circle' && (sched || !cfg.edit_hours || age < cfg.edit_hours * 3600)) html += mi('edit', 'edit', _t('Изменить'));
    if (txt && !cfg.protected) html += mi('copy', 'copy', _t('Копировать текст'));
    if (!sched && !cfg.protected) html += mi('forward', 'forward', _t('Переслать'));
    if (!sched && !cfg.protected && !cfg.saved) html += mi('save', 'bookmark', _t('В избранное'));
    if (!sched && cfg.can_pin) html += bub.classList.contains('is-pinned') ? mi('unpin', 'untack', _t('Открепить')) : mi('pin', 'tack', _t('Закрепить'));
    if (!sched) html += mi('hide', 'trash', _t('Удалить у себя'));
    if (!sched && (mine || cfg.admin)) html += mi('del', 'trash', _t('Удалить у всех'), 'bad');
    if (!html) return;
    msgMenu.innerHTML = html; msgMenu.hidden = false; msgMenu.dataset.id = bub.dataset.id;
    var w = msgMenu.offsetWidth, h = msgMenu.offsetHeight;
    msgMenu.style.left = Math.max(8, Math.min(x, innerWidth - w - 8)) + 'px';
    msgMenu.style.top = Math.max(8, Math.min(y, innerHeight - h - 8)) + 'px';
    msgMenu.classList.remove('pop'); void msgMenu.offsetWidth; msgMenu.classList.add('pop');
  }
  log.addEventListener('contextmenu', function (e) {
    var bub = e.target.closest('.bub[data-id]'); if (!bub || e.target.closest('a,video')) return;
    e.preventDefault(); openMsgMenu(bub, e.clientX, e.clientY);
  });
  var mlp = null, mlpAt = null;
  log.addEventListener('pointerdown', function (e) {
    if (e.pointerType === 'mouse') return;
    var bub = e.target.closest('.bub[data-id]'); if (!bub || e.target.closest('a,video,.voice,.circle,.rx')) return;
    var x = e.clientX, y = e.clientY; mlpAt = { x: x, y: y };
    mlp = setTimeout(function () { if (navigator.vibrate) navigator.vibrate(12); openMsgMenu(bub, x, y); }, 480);
  });
  log.addEventListener('pointermove', function (e) { if (mlpAt && Math.abs(e.clientX - mlpAt.x) + Math.abs(e.clientY - mlpAt.y) > 12) clearTimeout(mlp); });
  ['pointerup', 'pointercancel', 'scroll'].forEach(function (ev) { log.addEventListener(ev, function () { clearTimeout(mlp); }); });
  document.addEventListener('click', function (e) { if (!msgMenu.hidden && !e.target.closest('.msgmenu')) msgMenu.hidden = true; });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    msgMenu.hidden = true;
    if (replyBar && !replyBar.hidden) clearReply();
  });
  msgMenu.addEventListener('click', function (e) {
    var id = msgMenu.dataset.id, bub = bubOf(id);
    var rx = e.target.closest('[data-rx]');
    if (rx) { msgMenu.hidden = true; if (bub) react(id, rx.dataset.rx); return; }
    var b = e.target.closest('[data-m]'); if (!b) return;
    msgMenu.hidden = true;
    if (!bub) return;
    var m = b.dataset.m;
    if (m === 'copy') {
      var t = bub.querySelector('.bub__t');
      if (t && navigator.clipboard) navigator.clipboard.writeText(t.innerText).then(function () { toast(_t('Скопировано')); });
    } else if (m === 'reply') startReply(bub);
    else if (m === 'edit') startEdit(bub);
    else if (m === 'forward') openForward([id]);
    else if (m === 'save') post('/chat/forward/', { ids: [id], to: ['saved'] }).then(function () { toast(_t('Сохранено в «Избранное»')); }).catch(fail);
    else if (m === 'pin' || m === 'unpin') post('/chat/msg/' + id + '/' + m + '/').catch(fail);
    else if (m === 'hide') post('/chat/msg/' + id + '/hide/').then(function () { removeMsg(id); }).catch(fail);
    else if (m === 'del') {
      if (!confirm(_t('Удалить сообщение у всех?'))) return;
      post('/chat/msg/' + id + '/delete/').then(function () { removeMsg(id); }).catch(fail);
    }
  });

  /* ---------- переслать: выбор чатов ---------- */
  var fwdBox = document.getElementById('fwd-box'), fwdList = document.getElementById('fwd-list'), fwdIds = [], fwdTo = {};
  function closeForward() { if (fwdBox) fwdBox.hidden = true; }
  function openForward(ids) {
    if (!fwdBox) return;
    fwdIds = ids; fwdTo = {};
    document.getElementById('fwd-send').disabled = true; document.getElementById('fwd-hide').checked = false;
    fwdList.innerHTML = '<div class="fwdbox__load">' + _t('Загрузка…') + '</div>';
    fwdBox.hidden = false;
    fetch('/chat/pick/', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (j) {
      var html = '<button type="button" class="fwdbox__row" data-to="saved" data-q="' + esc(_t('Избранное').toLowerCase()) + '"><span class="tava tava--sm tava--saved">' + (IC.bookmark || '') + '</span><span>' + _t('Избранное') + '</span><i></i></button>';
      (j.items || []).forEach(function (c) {
        if (String(c.id) === String(cfg.thread) && cfg.saved) return;
        var ava = c.url ? '<img class="tava tava--sm" src="' + c.url + '" alt="">' : '<span class="tava tava--sm tava--h' + c.hue + '">' + esc(c.letter) + '</span>';
        html += '<button type="button" class="fwdbox__row" data-to="' + c.id + '" data-q="' + esc(c.name.toLowerCase()) + '">' + ava + '<span>' + esc(c.name) + '</span><i></i></button>';
      });
      fwdList.innerHTML = html;
    }).catch(function () { fwdList.innerHTML = '<div class="fwdbox__load">' + _t('Нет соединения — попробуйте ещё раз') + '</div>'; });
  }
  if (fwdBox) {
    fwdBox.addEventListener('click', function (e) { if (e.target === fwdBox) closeForward(); });
    document.getElementById('fwd-cancel').addEventListener('click', closeForward);
    document.getElementById('fwd-q').addEventListener('input', function () {
      var v = this.value.trim().toLowerCase();
      fwdList.querySelectorAll('.fwdbox__row').forEach(function (r) { r.hidden = v && r.dataset.q.indexOf(v) === -1; });
    });
    fwdList.addEventListener('click', function (e) {
      var r = e.target.closest('.fwdbox__row'); if (!r) return;
      var k = r.dataset.to;
      if (fwdTo[k]) delete fwdTo[k]; else if (Object.keys(fwdTo).length < 10) fwdTo[k] = 1;
      r.classList.toggle('on', !!fwdTo[k]);
      document.getElementById('fwd-send').disabled = !Object.keys(fwdTo).length;
    });
    document.getElementById('fwd-send').addEventListener('click', function () {
      var to = Object.keys(fwdTo); if (!to.length) return;
      this.disabled = true;
      post('/chat/forward/', { ids: fwdIds, to: to, hide: document.getElementById('fwd-hide').checked ? '1' : '' })
        .then(function () { closeForward(); toast(to.length > 1 ? _t('Переслано в несколько чатов') : _t('Переслано')); })
        .catch(function (e2) { fail(e2); document.getElementById('fwd-send').disabled = false; });
    });
  }

  /* ---------- поиск по чату ---------- */
  var srchBar = document.getElementById('srch-bar'), srchQ = document.getElementById('srch-q'), srchN = document.getElementById('srch-n');
  var found = [], foundAt = 0, srchT = null;
  function srchShow() {
    srchN.textContent = found.length ? (foundAt + 1) + ' / ' + found.length : (srchQ.value.trim().length > 1 ? _t('не найдено') : '');
    if (found.length) jump(found[foundAt].id);
  }
  function srchRun() {
    var v = srchQ.value.trim();
    if (v.length < 2) { found = []; srchN.textContent = ''; return; }
    fetch('/chat/' + cfg.thread + '/search/?q=' + encodeURIComponent(v), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); }).then(function (j) { found = j.items || []; foundAt = 0; srchShow(); })
      .catch(function () { srchN.textContent = ''; });
  }
  function srchOpen() {
    document.querySelectorAll('details.tg__chatmenu[open]').forEach(function (d) { d.open = false; });
    srchBar.hidden = false; srchQ.focus();
  }
  if (srchBar) {
    ['srch-open', 'srch-open2'].forEach(function (id) { var b = document.getElementById(id); if (b) b.addEventListener('click', srchOpen); });
    document.getElementById('srch-x').addEventListener('click', function () { srchBar.hidden = true; srchQ.value = ''; found = []; srchN.textContent = ''; });
    srchQ.addEventListener('input', function () { clearTimeout(srchT); srchT = setTimeout(srchRun, 350); });
    srchQ.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); if (found.length) { foundAt = (foundAt + 1) % found.length; srchShow(); } else srchRun(); } });
    document.getElementById('srch-up').addEventListener('click', function () { if (found.length) { foundAt = (foundAt + 1) % found.length; srchShow(); } });
    document.getElementById('srch-down').addEventListener('click', function () { if (found.length) { foundAt = (foundAt - 1 + found.length) % found.length; srchShow(); } });
    // поиск запомнен при переходе к далёкому сообщению (страница перезагружается)
    try {
      var keep = sessionStorage.getItem('ilm4.srch.' + cfg.thread);
      if (keep && cfg.at) { srchBar.hidden = false; srchQ.value = keep; }
      srchQ.addEventListener('input', function () { sessionStorage.setItem('ilm4.srch.' + cfg.thread, srchQ.value); });
      if (!cfg.at) sessionStorage.removeItem('ilm4.srch.' + cfg.thread);
    } catch (e) { /* приватный режим */ }
  }

  /* ---------- WebSocket с переподключением ---------- */
  var sock = null, queue = [];
  function connect() {
    var proto = location.protocol === 'https:' ? 'wss' : 'ws';
    try { sock = new WebSocket(proto + '://' + location.host + '/ws/chat/' + cfg.thread + '/'); } catch (e) { return; }
    sock.onopen = function () { while (queue.length) sock.send(queue.shift()); };
    sock.onmessage = function (e) {
      var d = JSON.parse(e.data);
      if (d.type === 'read') {
        (d.ids || []).forEach(function (id) { var t = log.querySelector('.bub[data-id="' + id + '"] .tick'); if (t) t.classList.add('tick--2'); });
        if (d.until) log.querySelectorAll('.bub--me').forEach(function (b) { var t = b.querySelector('.tick'); if (t && +b.dataset.ts <= d.until) t.classList.add('tick--2'); });
      } else if (d.type === 'del') {
        (d.ids || []).forEach(removeMsg);
      } else if (d.type === 'edit') {
        applyEdit(d);
      } else if (d.type === 'pin') {
        applyPin(d);
      } else if (d.type === 'reaction') {
        applyReaction(d);
      } else if (d.type === 'typing') {
        onTyping(d);
      } else if (d.type === 'signal') {
        Call.onSignal(d);
      } else if (d.type === 'error') {
        toast(d.error);
      } else {
        add(d);
      }
    };
    sock.onclose = function () { setTimeout(connect, 2000); };
  }
  function wsSend(obj) {
    var s = JSON.stringify(obj);
    if (sock && sock.readyState === 1) sock.send(s); else queue.push(s);
  }
  connect();

  /* ---------- текст: отправить, без звука, по расписанию ---------- */
  var recBtn = document.getElementById('rec-btn'), sendBtn = document.getElementById('send-btn');
  var sendMenu = document.getElementById('send-menu');
  function syncButtons() {
    var empty = !input.value.trim(), recording = form.classList.contains('is-recording');
    var showRec = !!recBtn && (empty || recording), showSend = !recording && !showRec;
    if (recBtn && recBtn.parentNode.hidden === showRec) {      // смена кнопок — с анимацией, как в Telegram
      var el = showRec ? recBtn : sendBtn;
      el.classList.remove('pop'); void el.offsetWidth; el.classList.add('pop');
    }
    if (recBtn) recBtn.parentNode.hidden = !showRec;
    sendBtn.hidden = !showSend;
  }
  function grow() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 140) + 'px'; }
  function sendText(opts) {
    var v = input.value.trim();
    if (!v) return false;
    if (editing) {                                        // правка: сохранить и вернуть поле ввода
      var eid = editing.id;
      post('/chat/msg/' + eid + '/edit/', { body: v }).then(function (j) { applyEdit(j); }).catch(fail);
      editing = null; input.value = ''; grow(); syncButtons(); clearReply(); saveDraft('');
      return true;
    }
    if (!(sock && sock.readyState === 1)) return false;   // запасной путь — обычная отправка формы
    var msg = { body: v };
    if (replyTo) { msg.reply_to = replyTo.id; clearReply(); }
    if (opts && opts.silent) msg.silent = true;
    if (opts && opts.schedule) msg.schedule = opts.schedule;
    wsSend(msg); input.value = ''; grow(); syncButtons(); draftLast = ''; clearTimeout(draftT);
    if (opts && opts.schedule) toast(_t('Сообщение запланировано'));
    else if (opts && opts.silent) toast(_t('Отправлено без звука'));
    return true;
  }
  form.addEventListener('submit', function (e) { if (sendText()) e.preventDefault(); });
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey && !('ontouchstart' in window)) {
      e.preventDefault(); if (!sendText() && input.value.trim()) form.submit();
    }
  });
  input.addEventListener('input', function () { grow(); syncButtons(); if (input.value.trim()) sayTyping('text'); draftSoon(); });
  // черновик: недописанное сохраняется и ждёт на любом устройстве (как в Telegram)
  var draftT = null, draftLast = input.value;
  function saveDraft(text) {
    if (text === draftLast || editing) return;
    draftLast = text;
    post('/chat/' + cfg.thread + '/draft/', { text: text }).catch(function () {});
  }
  function draftSoon() { clearTimeout(draftT); draftT = setTimeout(function () { saveDraft(input.value.trim()); }, 1500); }
  window.addEventListener('pagehide', function () {
    var text = editing ? '' : input.value.trim();
    if (text === draftLast || !navigator.sendBeacon) return;
    var fd = new FormData(); fd.append('text', text); fd.append('csrfmiddlewaretoken', csrf);
    navigator.sendBeacon('/chat/' + cfg.thread + '/draft/', fd);
  });
  if (input.value) { grow(); }
  document.querySelectorAll('[data-say]').forEach(function (b) {
    b.addEventListener('click', function () { input.value = b.dataset.say; grow(); syncButtons(); input.focus(); });
  });

  // меню у кнопки «Отправить»: правая кнопка мыши или долгое нажатие (как в Telegram)
  function openSendMenu() {
    if (!input.value.trim() || !sendMenu) return;
    sendMenu.hidden = false; sendMenu.classList.remove('pop'); void sendMenu.offsetWidth; sendMenu.classList.add('pop');
    sendMenu.querySelector('button').focus();
  }
  function closeSendMenu() { if (sendMenu) sendMenu.hidden = true; }
  if (sendBtn && sendMenu) {
    var lp = null, lpFired = false;
    sendBtn.addEventListener('contextmenu', function (e) { e.preventDefault(); openSendMenu(); });
    sendBtn.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse') return;
      lpFired = false; lp = setTimeout(function () { lpFired = true; openSendMenu(); }, 450);
    });
    ['pointerup', 'pointerleave', 'pointercancel'].forEach(function (ev) { sendBtn.addEventListener(ev, function () { clearTimeout(lp); }); });
    sendBtn.addEventListener('click', function (e) { if (lpFired) { e.preventDefault(); lpFired = false; } });
    document.addEventListener('click', function (e) { if (!sendMenu.hidden && !e.target.closest('#send-menu')) closeSendMenu(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { closeSendMenu(); closeSched(); } });
    sendMenu.addEventListener('click', function (e) {
      var b = e.target.closest('[data-send]'); if (!b) return;
      closeSendMenu();
      if (b.dataset.send === 'silent') sendText({ silent: true }); else openSched();
    });
  }

  // окно «Запланировать»
  var schedBox = document.getElementById('sched-box'), schedAt = document.getElementById('sched-at');
  function localValue(d) {
    var p = function (n) { return ('0' + n).slice(-2); };
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + 'T' + p(d.getHours()) + ':' + p(d.getMinutes());
  }
  function openSched() {
    if (!schedBox) return;
    var d = new Date(Date.now() + 3600e3); d.setSeconds(0, 0);
    schedAt.value = localValue(d); schedAt.min = localValue(new Date());
    schedBox.hidden = false; schedAt.focus();
  }
  function closeSched() { if (schedBox) schedBox.hidden = true; }
  if (schedBox) {
    document.getElementById('sched-cancel').addEventListener('click', closeSched);
    schedBox.addEventListener('click', function (e) {
      if (e.target === schedBox) { closeSched(); return; }
      var q = e.target.closest('[data-in],[data-at],[data-tomorrow]'); if (!q) return;
      var d = new Date(); d.setSeconds(0, 0);
      if (q.dataset.in) d = new Date(Date.now() + q.dataset.in * 60e3);
      if (q.dataset.at) { d.setHours(+q.dataset.at, 0); if (d < new Date()) d.setDate(d.getDate() + 1); }
      if (q.dataset.tomorrow) { d.setDate(d.getDate() + 1); d.setHours(+q.dataset.tomorrow, 0); }
      schedAt.value = localValue(d);
    });
    document.getElementById('sched-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var when = new Date(schedAt.value);
      if (isNaN(when) || when < new Date(Date.now() + 60e3)) { toast(_t('Выберите время хотя бы через минуту')); return; }
      if (sendText({ schedule: when.toISOString(), silent: document.getElementById('sched-silent').checked })) closeSched();
    });
  }
  syncButtons();

  /* ---------- загрузка вложений ---------- */
  var BIG = 16 * 1048576;       // крупнее — частями по 4 МБ: виден прогресс, обрыв связи не начинает заново
  function upload(kind, blob, duration, name) {
    if ((kind === 'file' || kind === 'video') && blob.size > BIG) return uploadBig(kind, blob, duration, name);
    var fd = new FormData();
    fd.append('kind', kind); fd.append('file', blob, name || kind);
    if (duration) fd.append('duration', String(Math.round(duration)));
    if (replyTo) { fd.append('reply_to', replyTo.id); clearReply(); }
    var bar = document.createElement('div'); bar.className = 'tg__uploading'; bar.textContent = _t('Отправка…');
    log.appendChild(bar); toBottom();
    return fetch('/chat/' + cfg.thread + '/upload/', { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-CSRFToken': csrf } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) { bar.remove(); if (!res.ok) { toast(res.j.error || _t('Не удалось отправить')); return; } add(res.j); })
      .catch(function () { bar.remove(); toast(_t('Нет соединения — попробуйте ещё раз')); });
  }
  function uploadBig(kind, file, duration, name) {
    var bar = document.createElement('div'); bar.className = 'tg__uploading tg__uploading--big';
    bar.innerHTML = '<span class="tg__upname"></span><span class="tg__upbar"><i></i></span><span class="tg__uppct">0%</span>' +
      '<button type="button" class="tg__upx" aria-label="' + _t('Отменить') + '">×</button>';
    bar.querySelector('.tg__upname').textContent = name || _t('Файл');
    log.appendChild(bar); toBottom();
    var fill = bar.querySelector('i'), pct = bar.querySelector('.tg__uppct');
    var id = null, stopped = false, hdr = { 'X-CSRFToken': csrf };
    function show(done) {
      var p = Math.min(100, Math.floor(done / file.size * 100));
      fill.style.width = p + '%'; pct.textContent = p + '% · ' + fsize(done) + ' / ' + fsize(file.size);
    }
    function fail(text) { bar.remove(); if (!stopped) toast(text || _t('Не удалось отправить')); }
    function call(url, opts) {
      opts = opts || {}; opts.credentials = 'same-origin'; opts.headers = Object.assign({}, hdr, opts.headers || {});
      return fetch(url, opts).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, status: r.status, j: j }; }); });
    }
    bar.querySelector('.tg__upx').addEventListener('click', function () {
      stopped = true; bar.remove();
      if (id) call('/chat/upload/' + id + '/cancel/', { method: 'POST' }).catch(function () {});
    });
    function part(offset, size, tries) {
      if (stopped) return;
      if (offset >= file.size) {
        return call('/chat/upload/' + id + '/finish/', { method: 'POST' }).then(function (res) {
          bar.remove(); if (!res.ok) { toast(res.j.error || _t('Не удалось отправить')); return; } add(res.j);
        }).catch(function () { retry(offset, size, tries); });
      }
      return call('/chat/upload/' + id + '/part/?offset=' + offset, {
        method: 'POST', body: file.slice(offset, offset + size), headers: { 'Content-Type': 'application/octet-stream' }
      }).then(function (res) {
        if (res.ok || res.status === 409) {            // 409 — сервер подсказал, с какого места продолжать
          var got = res.j.received; if (typeof got !== 'number') return fail(res.j.error);
          show(got); return part(got, size, 0);
        }
        fail(res.j.error);
      }).catch(function () { retry(offset, size, tries); });
    }
    function retry(offset, size, tries) {              // связь пропала: ждём и продолжаем с того же места
      if (stopped) return;
      if (tries >= 8) return fail(_t('Нет соединения — попробуйте ещё раз'));
      pct.textContent = _t('Нет связи, пробую ещё раз…');
      setTimeout(function () {
        call('/chat/upload/' + id + '/').then(function (res) {
          if (!res.ok) return fail(res.j.error);
          show(res.j.received); part(res.j.received, size, tries + 1);
        }).catch(function () { retry(offset, size, tries + 1); });
      }, Math.min(15000, 1500 * (tries + 1)));
    }
    var fd = new FormData();
    fd.append('kind', kind); fd.append('name', name || file.name || kind); fd.append('size', String(file.size));
    if (duration) fd.append('duration', String(Math.round(duration)));
    if (replyTo) { fd.append('reply_to', replyTo.id); clearReply(); }
    return call('/chat/' + cfg.thread + '/upload/begin/', { method: 'POST', body: fd }).then(function (res) {
      if (!res.ok) return fail(res.j.error);
      id = res.j.upload; part(0, res.j.part, 0);
    }).catch(function () { fail(_t('Нет соединения — попробуйте ещё раз')); });
  }
  // «скрепка»: фото/видео (сжимается) или файл (как есть) — как в Telegram
  var attachBtn = document.getElementById('attach-btn'), attachMenu = document.getElementById('attach-menu');
  var fileInput = document.getElementById('file-input');
  if (attachBtn) {
    attachBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      var items = attachMenu.querySelectorAll('[data-attach]');
      if (items.length === 1) { items[0].click(); return; }
      attachMenu.hidden = !attachMenu.hidden;
      if (!attachMenu.hidden) { attachMenu.classList.remove('pop'); void attachMenu.offsetWidth; attachMenu.classList.add('pop'); }
    });
    attachMenu.addEventListener('click', function (e) {
      var b = e.target.closest('[data-attach]'); if (!b) return;
      attachMenu.hidden = true;
      (b.dataset.attach === 'file' ? fileInput : document.getElementById('photo-input')).click();
    });
    document.addEventListener('click', function (e) { if (!attachMenu.hidden && !e.target.closest('#attach-menu')) attachMenu.hidden = true; });
  }
  if (fileInput) fileInput.addEventListener('change', function () {
    var f = fileInput.files[0];
    fileInput.value = '';
    if (!f) return;
    if (f.size > (F.file_max_mb || 2000) * 1048576) { toast(_t('Файл слишком большой')); return; }
    upload('file', f, 0, f.name);
  });
  // кнопки карточки объявления: «Отправить моё резюме» и т.п.
  document.querySelectorAll('[data-say-now]').forEach(function (b) {
    b.addEventListener('click', function () {
      input.value = b.dataset.sayNow.replace('{link}', location.origin + b.dataset.path);
      if (!sendText()) form.submit();
    });
  });
  var photoInput = document.getElementById('photo-input');
  if (photoInput) photoInput.addEventListener('change', function () {
    var f = photoInput.files[0];
    photoInput.value = '';
    if (!f) return;
    if (!/^video\//.test(f.type)) {
      // как в Telegram: перед отправкой фото можно порисовать и подписать
      if (window.ilm4PhotoEdit && !/gif$/.test(f.type)) window.ilm4PhotoEdit(f).then(function (r) { if (r) upload('photo', r, 0, r.name); });
      else upload('photo', f, 0, f.name);
      return;
    }
    if (f.size > (F.file_max_mb || 2000) * 1048576) { toast(_t('Файл слишком большой')); return; }
    // длительность — из метаданных файла (сервер всё равно ограничит 5 минутами)
    var v = document.createElement('video'), u = URL.createObjectURL(f), done = false;
    function go(sec) { if (done) return; done = true; URL.revokeObjectURL(u); upload('video', f, sec, f.name); }
    v.preload = 'metadata';
    v.onloadedmetadata = function () { go(isFinite(v.duration) ? v.duration : 0); };
    v.onerror = function () { go(0); };
    setTimeout(function () { go(0); }, 3000);
    v.src = u;
  });

  function pickMime(list) {
    if (!window.MediaRecorder) return null;
    for (var i = 0; i < list.length; i++) if (MediaRecorder.isTypeSupported(list[i])) return list[i];
    return '';
  }

  /* ---------- запись: одна кнопка «голос / кружок», как в Telegram ----------
     нажать — переключить голос ↔ кружок; удерживать — запись; отпустить — отправить;
     увести влево — отмена; увести вверх — «замок» (запись без рук, отправка кнопкой ➤). */
  function stopTracks(stream) { if (stream) stream.getTracks().forEach(function (t) { t.stop(); }); }
  var R = null;                                   // текущая запись
  var recTime = document.getElementById('rec-time'), recSlide = document.getElementById('rec-slide');
  var recLock = document.getElementById('rec-lock'), recCancel = document.getElementById('rec-cancel');
  var circleBox = document.getElementById('circle-rec'), recPause = document.getElementById('rec-pause');
  // кружок снимается поверх переписки, а панель с таймером и кнопкой остаётся видна — как в Telegram
  if (circleBox && document.getElementById('chat-main')) document.getElementById('chat-main').appendChild(circleBox);
  function recSeconds(r) { return (Date.now() - r.t0 - r.idle - (r.pausedAt ? Date.now() - r.pausedAt : 0)) / 1000; }
  function recClock(s) { return Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0') + ',' + Math.floor((s * 10) % 10); }
  var CANCEL_DX = -110, LOCK_DY = -70, HOLD_MS = 220;
  var LIMIT = { voice: 300, circle: 60 };

  function setMode(mode) {
    recBtn.dataset.mode = mode;
    recBtn.classList.remove('flip'); void recBtn.offsetWidth; recBtn.classList.add('flip');
  }
  function recUI(on) {
    form.classList.toggle('is-recording', on);
    if (!on) form.classList.remove('is-locked', 'is-paused');
    if (!on) { recBtn.style.removeProperty('--dx'); recBtn.style.removeProperty('--dy'); }
    recBtn.classList.toggle('is-rec', on);
    syncButtons();
  }
  function startRec(mode, locked) {
    var voice = mode === 'voice';
    var mime = pickMime(voice ? ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
      : ['video/mp4;codecs=avc1,mp4a', 'video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm']);
    if (mime === null || !navigator.mediaDevices) {
      toast(voice ? _t('Запись голоса не поддерживается в этом браузере') : _t('Видеозапись не поддерживается в этом браузере'));
      return;
    }
    R = { mode: mode, ready: false, cancelled: false, locked: !!locked, chunks: [], idle: 0, pausedAt: 0 };
    form.classList.toggle('is-circle', !voice);
    var r = R;
    recUI(true); if (locked) form.classList.add('is-locked');
    navigator.mediaDevices.getUserMedia(voice ? { audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } }
      : { audio: true, video: { facingMode: 'user', width: { ideal: 480 }, height: { ideal: 480 } } })
      .then(function (stream) {
        if (r !== R || r.cancelled) { stopTracks(stream); return; }   // отпустили раньше, чем дали доступ
        r.stream = stream;
        // голос — 32 кбит/с (как в Telegram: речь звучит так же, файл в несколько раз меньше); кружок — ~0,9 Мбит/с
        var opts = voice ? { audioBitsPerSecond: 32000 } : { videoBitsPerSecond: 900000, audioBitsPerSecond: 48000 };
        if (mime) opts.mimeType = mime;
        r.mr = new MediaRecorder(stream, opts);
        r.mr.ondataavailable = function (e) { if (e.data.size) r.chunks.push(e.data); };
        r.mr.onstop = function () {
          stopTracks(stream);
          if (!voice) { document.getElementById('circle-preview').srcObject = null; circleBox.hidden = true; }
          var sec = r.sec;
          if (r.send && sec >= 1) upload(mode, new Blob(r.chunks, { type: r.mr.mimeType || mime }), sec);
          else if (r.send) toast(_t('Слишком коротко — удерживайте кнопку'));
        };
        if (!voice) {
          document.getElementById('circle-preview').srcObject = stream;
          circleBox.hidden = false; circleBox.classList.toggle('is-locked', r.locked);
        }
        r.t0 = Date.now(); r.ready = true; r.mr.start(250);
        typingSent = 0; sayTyping(voice ? 'voice' : 'circle');
        if (navigator.vibrate) navigator.vibrate(15);
        tickRec(r);
      })
      .catch(function () {
        if (r === R) { R = null; recUI(false); }
        toast(voice ? _t('Нет доступа к микрофону — разрешите его в настройках браузера') : _t('Нет доступа к камере или микрофону'));
      });
  }
  function tickRec(r) {
    if (r !== R) return;
    var s = recSeconds(r);
    recTime.textContent = recClock(s);
    if (r.mode === 'circle') {
      var ring = document.getElementById('circle-ring'), L = 2 * Math.PI * 48;
      ring.style.strokeDasharray = L; ring.style.strokeDashoffset = L * (1 - Math.min(s / 60, 1));
    }
    if (s >= LIMIT[r.mode]) { finishRec(true); return; }
    requestAnimationFrame(function () { tickRec(r); });
  }
  function finishRec(send) {
    var r = R; if (!r) return;
    R = null; r.send = send; r.cancelled = !send;
    r.sec = r.t0 ? recSeconds(r) : 0;
    recUI(false);
    recSlide.style.transform = ''; recSlide.style.opacity = ''; recLock.style.transform = '';
    if (r.mr && r.mr.state !== 'inactive') r.mr.stop();
    else if (!r.ready && send) toast(_t('Удерживайте кнопку, чтобы записать'));
    if (r.mode === 'circle' && !r.mr) circleBox.hidden = true;
  }
  function lockRec() {
    if (!R || R.locked) return;
    R.locked = true; form.classList.add('is-locked'); circleBox.classList.add('is-locked');
    recBtn.style.removeProperty('--dx'); recBtn.style.removeProperty('--dy');
    recSlide.style.transform = ''; recSlide.style.opacity = '';
    if (navigator.vibrate) navigator.vibrate(10);
  }

  if (recBtn) {
    var both = recBtn.dataset.both === '1', press = null;
    recBtn.addEventListener('pointerdown', function (e) {
      if (e.button > 0) return;
      if (R && R.locked) return;                       // в «замке» кнопка — «отправить»
      e.preventDefault();
      recBtn.setPointerCapture(e.pointerId);
      press = { x: e.clientX, y: e.clientY, id: e.pointerId, holding: false };
      press.t = setTimeout(function () { if (press) { press.holding = true; startRec(recBtn.dataset.mode); } }, HOLD_MS);
    });
    recBtn.addEventListener('pointermove', function (e) {
      if (!press || !press.holding || !R || R.locked) return;
      var dx = Math.min(0, e.clientX - press.x), dy = Math.min(0, e.clientY - press.y);
      recSlide.style.transform = 'translateX(' + Math.max(dx, CANCEL_DX) + 'px)';
      recSlide.style.opacity = String(1 - Math.min(1, dx / CANCEL_DX) * 0.7);
      recLock.style.transform = 'translateY(' + Math.max(dy, LOCK_DY) / 2 + 'px)';
      recBtn.style.setProperty('--dx', Math.max(dx, CANCEL_DX) + 'px');           // кнопка едет за пальцем
      recBtn.style.setProperty('--dy', Math.max(dy, LOCK_DY) + 'px');
      if (dx <= CANCEL_DX) { press = null; finishRec(false); toast(_t('Запись отменена')); }
      else if (dy <= LOCK_DY) { lockRec(); press = null; }
    });
    function release(e) {
      if (!press) return;
      clearTimeout(press.t);
      var wasHolding = press.holding; press = null;
      if (e.type === 'pointercancel') { if (wasHolding) finishRec(false); return; }
      if (!wasHolding) { if (both) setMode(recBtn.dataset.mode === 'voice' ? 'circle' : 'voice'); return; }   // короткое нажатие
      if (R && !R.locked) finishRec(true);
    }
    recBtn.addEventListener('pointerup', release);
    recBtn.addEventListener('pointercancel', release);
    recBtn.addEventListener('click', function () { if (R && R.locked) finishRec(true); });   // ➤ в «замке»
    recBtn.addEventListener('keydown', function (e) {          // с клавиатуры: Enter/Пробел — запись без рук
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      if (R && R.locked) finishRec(true); else if (!R) startRec(recBtn.dataset.mode, true);
    });
  }
  if (recCancel) recCancel.addEventListener('click', function () { finishRec(false); });
  // пауза в «замке»: остановить и продолжить запись (время на паузе не считается)
  if (recPause) recPause.addEventListener('click', function () {
    var r = R;
    if (!r || !r.mr || !r.locked || !r.mr.pause) return;
    if (r.pausedAt) { r.idle += Date.now() - r.pausedAt; r.pausedAt = 0; r.mr.resume(); }
    else { r.pausedAt = Date.now(); r.mr.pause(); }
    form.classList.toggle('is-paused', !!r.pausedAt);
  });
  var cSend = document.getElementById('circle-send'), cCancel = document.getElementById('circle-cancel');
  if (cSend) cSend.addEventListener('click', function () { finishRec(true); });
  if (cCancel) cCancel.addEventListener('click', function () { finishRec(false); });

  /* ---------- оформление выделенного текста: жирный, курсив, зачёркнутый, код, скрытый ---------- */
  var fmtBar = document.getElementById('fmt-bar');
  if (fmtBar && input) {
    var fmtSync = function () { fmtBar.hidden = document.activeElement !== input || input.selectionStart === input.selectionEnd; };
    ['select', 'keyup', 'mouseup', 'touchend', 'blur', 'input'].forEach(function (ev) { input.addEventListener(ev, function () { setTimeout(fmtSync, 0); }); });
    document.addEventListener('selectionchange', fmtSync);
    fmtBar.addEventListener('mousedown', function (e) { e.preventDefault(); });       // не терять выделение
    fmtBar.addEventListener('click', function (e) {
      var b = e.target.closest('[data-fmt]'); if (!b) return;
      var m = b.dataset.fmt, a = input.selectionStart, z = input.selectionEnd, v = input.value;
      if (a === z) return;
      input.value = v.slice(0, a) + m + v.slice(a, z) + m + v.slice(z);
      input.setSelectionRange(z + m.length * 2, z + m.length * 2);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      fmtBar.hidden = true;
    });
  }

  /* ---------- свои запланированные: отправить сейчас / удалить ---------- */
  log.addEventListener('click', function (e) {
    var b = e.target.closest('[data-sched-act]'); if (!b) return;
    var bub = b.closest('.bub'), act = b.dataset.schedAct;
    fetch('/chat/msg/' + bub.dataset.id + '/' + act + '/', { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrf } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) { toast(res.j.error || _t('Не удалось')); return; }
        if (act === 'cancel') { bub.classList.add('bub--out'); setTimeout(function () { bub.remove(); }, 200); }
        else add(res.j);
      }).catch(function () { toast(_t('Нет соединения — попробуйте ещё раз')); });
  });

  /* ---------- проигрывание голосовых и кружков ---------- */
  var playing = null;
  function stopPlaying() { if (playing) { playing.pause(); playing = null; } }
  var SPEEDS = [1, 1.5, 2];
  log.addEventListener('click', function (e) {
    var sp = e.target.closest('.voice__sp');
    if (sp) {                                         // скорость голосового: 1× → 1,5× → 2×
      var box = sp.closest('.voice'), next = SPEEDS[(SPEEDS.indexOf(+box.dataset.rate || 1) + 1) % SPEEDS.length];
      box.dataset.rate = next; sp.textContent = String(next).replace('.', ',') + '×';
      if (box._a) box._a.playbackRate = next;
      return;
    }
    var v = e.target.closest('.voice');
    if (v) {
      var btn = v.querySelector('.voice__play'), fill = v.querySelector('.voice__bar i'), tEl = v.querySelector('.voice__t');
      if (!v._a) {
        v._a = new Audio(v.dataset.src);
        v._a.addEventListener('timeupdate', function () {
          if (v._a.duration) fill.style.width = (v._a.currentTime / v._a.duration * 100) + '%';
          tEl.textContent = mmss(v._a.currentTime);
        });
        v._a.addEventListener('ended', function () { btn.innerHTML = ICON.play; fill.style.width = '0'; playing = null; });
        v._a.addEventListener('pause', function () { btn.innerHTML = ICON.play; });
        v._a.addEventListener('play', function () { btn.innerHTML = ICON.pause; });
      }
      v._a.playbackRate = +v.dataset.rate || 1;
      if (v._a.paused) { stopPlaying(); v._a.play(); playing = v._a; } else { v._a.pause(); playing = null; }
      return;
    }
    var c = e.target.closest('.circle');
    if (c) {
      var vid = c.querySelector('video');
      if (vid.paused) { stopPlaying(); vid.muted = false; vid.play(); playing = vid; c.classList.add('is-playing'); }
      else { vid.pause(); playing = null; c.classList.remove('is-playing'); }
      vid.onended = function () { c.classList.remove('is-playing'); playing = null; };
    }
  });

  /* ---------- звонки (WebRTC) ---------- */
  var Call = (function () {
    var el = document.getElementById('call');
    var stateEl = document.getElementById('call-state');
    var remoteV = document.getElementById('call-remote'), localV = document.getElementById('call-local');
    var audioEl = document.getElementById('call-audio');
    var bAccept = document.getElementById('call-accept'), bEnd = document.getElementById('call-end');
    var bMute = document.getElementById('call-mute'), bCam = document.getElementById('call-cam');
    var ice = [{ urls: ['stun:stun.l.google.com:19302', 'stun:stun1.l.google.com:19302'] }];
    if (F.turn && F.turn.url) ice.push({ urls: F.turn.url, username: F.turn.username, credential: F.turn.credential });
    var c = null;   // текущий звонок
    var autoAnswer = /[?&]answer=1/.test(location.search);

    function ui(state, text) {
      el.hidden = false;
      el.classList.toggle('call--video', !!(c && c.video));
      el.className = el.className.replace(/\bcall--s-\w+/g, '') + ' call--s-' + state;
      stateEl.textContent = text;
      bAccept.hidden = state !== 'incoming';
      bCam.hidden = !(c && c.video);
    }
    function media(video) {
      return navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true },
        video: video ? { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } } : false });
    }
    function peer() {
      var pc = new RTCPeerConnection({ iceServers: ice });
      c.local.getTracks().forEach(function (t) { pc.addTrack(t, c.local); });
      pc.onicecandidate = function (e) { if (e.candidate) wsSend({ type: 'signal', action: 'ice', candidate: e.candidate }); };
      pc.ontrack = function (e) {
        if (c.video) remoteV.srcObject = e.streams[0]; else audioEl.srcObject = e.streams[0];
      };
      pc.onconnectionstatechange = function () {
        if (!c) return;
        if (pc.connectionState === 'connected' && !c.start) { c.start = Date.now(); tick(); showEmoji(pc); }
        if (pc.connectionState === 'failed') { toast(_t('Не удалось соединиться. Возможно, нужна настройка TURN-сервера.')); finish(true); }
      };
      c.pc = pc;
      return pc;
    }
    /* 4 эмодзи из отпечатков ключей обеих сторон: одинаковые у обоих — посередине никого нет */
    var emojiBtn = document.getElementById('call-emoji'), emojiInfo = document.getElementById('call-emoji-info');
    function showEmoji(pc) {
      if (!window.ilmCallEmoji || !emojiBtn) return;
      window.ilmCallEmoji(pc.localDescription && pc.localDescription.sdp, pc.remoteDescription && pc.remoteDescription.sdp)
        .then(function (list) {
          if (!c || !list.length) return;
          emojiBtn.textContent = list.join(' '); emojiBtn.hidden = false; emojiBtn.classList.add('is-new');
        });
    }
    if (emojiBtn) emojiBtn.addEventListener('click', function () { emojiInfo.hidden = !emojiInfo.hidden; });
    function tick() {
      if (!c || !c.start) return;
      ui('active', mmss((Date.now() - c.start) / 1000));
      c.tickT = setTimeout(tick, 1000);
    }
    function flushIce() { (c.pendingIce || []).forEach(function (x) { c.pc.addIceCandidate(x).catch(function () {}); }); c.pendingIce = []; }
    function cleanup() {
      if (!c) return;
      clearInterval(c.ringT); clearTimeout(c.timeoutT); clearTimeout(c.tickT);
      if (c.pc) c.pc.close();
      stopTracks(c.local);
      remoteV.srcObject = null; localV.srcObject = null; audioEl.srcObject = null;
      if (emojiBtn) { emojiBtn.hidden = true; emojiBtn.classList.remove('is-new'); emojiInfo.hidden = true; }
      c = null; el.hidden = true;
    }
    function finish(sendEnd, outcome) {
      if (!c) return;
      if (sendEnd) wsSend({ type: 'signal', action: 'end' });
      if (c.role === 'caller') {
        var dur = c.start ? (Date.now() - c.start) / 1000 : 0;
        wsSend({ type: 'calllog', video: c.video, duration: Math.round(dur), outcome: outcome || (c.start ? 'done' : 'cancelled') });
      }
      cleanup();
    }

    function start(video) {
      if (c) return;
      if (!window.RTCPeerConnection || !navigator.mediaDevices) { toast(_t('Звонки не поддерживаются в этом браузере')); return; }
      c = { role: 'caller', video: video, pendingIce: [] };
      ui('ringing', video ? _t('Доступ к камере…') : _t('Доступ к микрофону…'));
      media(video).then(function (stream) {
        if (!c) { stopTracks(stream); return; }
        c.local = stream; if (video) localV.srcObject = stream;
        ui('ringing', _t('Звоним…'));
        var ring = function () { wsSend({ type: 'signal', action: 'ring', video: video }); };
        ring(); c.ringT = setInterval(ring, 3000);   // повтор: собеседник мог открыть страницу позже
        c.timeoutT = setTimeout(function () { finish(true, 'missed'); toast(_t('Не отвечает')); }, 45000);
      }).catch(function () { cleanup(); toast(video ? _t('Нет доступа к камере') : _t('Нет доступа к микрофону')); });
    }
    function accept() {
      if (!c || c.role !== 'callee') return;
      ui('connecting', _t('Соединение…'));
      media(c.video).then(function (stream) {
        if (!c) { stopTracks(stream); return; }
        c.local = stream; if (c.video) localV.srcObject = stream;
        wsSend({ type: 'signal', action: 'accept' });
      }).catch(function () { toast(c.video ? _t('Нет доступа к камере') : _t('Нет доступа к микрофону')); decline(); });
    }
    function decline() { if (!c) return; wsSend({ type: 'signal', action: 'decline' }); cleanup(); }

    function onSignal(d) {
      var a = d.action;
      if (a === 'ring') {
        if (c) return;                       // уже в звонке / повтор сигнала
        c = { role: 'callee', video: !!d.video, pendingIce: [] };
        ui('incoming', d.video ? _t('Входящий видеозвонок') : _t('Входящий аудиозвонок'));
        if (autoAnswer) { autoAnswer = false; accept(); }
        return;
      }
      if (!c) return;
      if (a === 'accept' && c.role === 'caller' && !c.pc) {
        clearInterval(c.ringT); clearTimeout(c.timeoutT);
        ui('connecting', _t('Соединение…'));
        var pc = peer();
        pc.createOffer().then(function (o) { return pc.setLocalDescription(o); })
          .then(function () { wsSend({ type: 'signal', action: 'offer', sdp: pc.localDescription }); });
      } else if (a === 'offer' && c.role === 'callee') {
        var pc2 = peer();
        pc2.setRemoteDescription(d.sdp).then(function () { flushIce(); return pc2.createAnswer(); })
          .then(function (ans) { return pc2.setLocalDescription(ans); })
          .then(function () { wsSend({ type: 'signal', action: 'answer', sdp: pc2.localDescription }); });
      } else if (a === 'answer' && c.role === 'caller' && c.pc) {
        c.pc.setRemoteDescription(d.sdp).then(flushIce);
      } else if (a === 'ice') {
        if (c.pc && c.pc.remoteDescription) c.pc.addIceCandidate(d.candidate).catch(function () {});
        else c.pendingIce.push(d.candidate);
      } else if (a === 'decline') {
        toast(_t('Звонок отклонён')); finish(false, 'declined');
      } else if (a === 'end') {
        finish(false);
      }
    }

    document.querySelectorAll('[data-call]').forEach(function (b) {
      b.addEventListener('click', function () { start(b.dataset.call === 'video'); });
    });
    // пришли из профиля по кнопке «Звонок» / «Видео» — сразу звоним (ждём, пока подключится чат)
    var want = new URLSearchParams(location.search).get('call');
    if (want === 'audio' || want === 'video') {
      history.replaceState(null, '', location.pathname);
      setTimeout(function () { var b = document.querySelector('[data-call="' + want + '"]'); if (b) b.click(); }, 1200);
    }
    bAccept.addEventListener('click', accept);
    bEnd.addEventListener('click', function () {
      if (!c) return;
      if (c.role === 'callee' && !c.pc) decline(); else finish(true);
    });
    bMute.addEventListener('click', function () {
      if (!c || !c.local) return;
      var t = c.local.getAudioTracks()[0]; if (!t) return;
      t.enabled = !t.enabled; bMute.classList.toggle('off', !t.enabled);
    });
    bCam.addEventListener('click', function () {
      if (!c || !c.local) return;
      var t = c.local.getVideoTracks()[0]; if (!t) return;
      t.enabled = !t.enabled; bCam.classList.toggle('off', !t.enabled);
    });
    window.addEventListener('beforeunload', function () { if (c) finish(true); });
    return { onSignal: onSignal };
  })();

  if (cfg.at) {
    var target = log.querySelector('[data-id="' + cfg.at + '"]');
    if (target) { target.scrollIntoView({ block: 'center' }); target.classList.add('is-flash'); if (downBtn) downBtn.hidden = false; } else toBottom();
  } else toBottom();
})();
