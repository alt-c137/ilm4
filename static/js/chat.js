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
    return (n / 1048576).toFixed(1).replace('.0', '') + ' ' + _t('МБ');
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
    call: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 3.5h3l1.5 4-2 1.5a12 12 0 0 0 6 6l1.5-2 4 1.5v3a2 2 0 0 1-2.2 2A16.5 16.5 0 0 1 4.5 5.7 2 2 0 0 1 6.5 3.5z"/></svg>'
  };

  /* ---------- вывод сообщений ---------- */
  function lastDay() { var d = log.querySelectorAll('.tg__day'); return d.length ? d[d.length - 1].dataset.day : ''; }
  function msgHTML(d, mine) {
    if (d.kind === 'system') return '<div class="tg__sys" data-id="' + d.id + '"><span>' + ICON.call + esc(d.body) + ' · ' + esc(d.time) + '</span></div>';
    var media = '';
    if (d.kind === 'photo') media = '<a class="bub__photo" href="' + d.url + '" target="_blank" rel="noopener"><img src="' + d.url + '" alt="' + _t('Фото') + '"></a>';
    if (d.kind === 'voice') media = '<div class="voice" data-src="' + d.url + '"><button type="button" class="voice__play" aria-label="' + _t('Слушать') + '">' + ICON.play + '</button><span class="voice__bar"><i></i></span><span class="voice__t">' + mmss(d.duration) + '</span></div>';
    if (d.kind === 'video') media = '<div class="bub__video"><video src="' + d.url + '" controls preload="metadata" playsinline></video></div>';
    if (d.kind === 'file') media = '<a class="bub__file" href="' + d.url + '" download><span class="bub__fileico">' + ICON.clip + '</span><span class="bub__fileb"><b>' + esc(d.file_name || _t('Файл')) + '</b><small>' + fsize(d.file_size) + '</small></span></a>';
    if (d.kind === 'circle') media = '<div class="circle" data-src="' + d.url + '"><video src="' + d.url + '" preload="metadata" playsinline></video><span class="circle__t">' + mmss(d.duration) + '</span><span class="circle__play">' + ICON.play + '</span></div>';
    var sched = d.scheduled ? '<span class="bub__sched">' + ICON.clock + _t('отправится') + ' ' + esc(d.scheduled_label) + '</span>' +
      '<span class="bub__schedact"><button type="button" data-sched-act="send">' + _t('Отправить сейчас') + '</button>' +
      '<button type="button" data-sched-act="cancel">' + _t('Удалить') + '</button></span>' : '';
    return '<div class="bub bub--in bub--' + d.kind + (mine ? ' bub--me' : '') + (d.scheduled ? ' bub--sched' : '') +
      ' bub--tail" data-id="' + d.id + '">' + media +
      (d.body ? '<span class="bub__t">' + esc(d.body) + '</span>' : '') + sched +
      '<span class="bub__meta">' + (d.scheduled ? '' : esc(d.time || '')) + (mine && !d.scheduled ? '<span class="tick"></span>' : '') + '</span></div>';
  }
  function add(d) {
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
    if (d.warn && !mine && cfg.warn_text) {        // просят предоплату — предупреждаем получателя
      log.insertAdjacentHTML('beforeend', '<div class="tg__warn bub--in">' + ICON.shield + esc(cfg.warn_text) + '</div>');
    }
    toBottom();
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
    if (!(sock && sock.readyState === 1)) return false;   // запасной путь — обычная отправка формы
    var msg = { body: v };
    if (opts && opts.silent) msg.silent = true;
    if (opts && opts.schedule) msg.schedule = opts.schedule;
    wsSend(msg); input.value = ''; grow(); syncButtons();
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
  input.addEventListener('input', function () { grow(); syncButtons(); });
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
  function upload(kind, blob, duration, name) {
    var fd = new FormData();
    fd.append('kind', kind); fd.append('file', blob, name || kind);
    if (duration) fd.append('duration', String(Math.round(duration)));
    var bar = document.createElement('div'); bar.className = 'tg__uploading'; bar.textContent = _t('Отправка…');
    log.appendChild(bar); toBottom();
    return fetch('/chat/' + cfg.thread + '/upload/', { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-CSRFToken': csrf } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) { bar.remove(); if (!res.ok) { toast(res.j.error || _t('Не удалось отправить')); return; } add(res.j); })
      .catch(function () { bar.remove(); toast(_t('Нет соединения — попробуйте ещё раз')); });
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
    if (f.size > (F.file_max_mb || 100) * 1048576) { toast(_t('Файл слишком большой')); return; }
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
    if (!/^video\//.test(f.type)) { upload('photo', f, 0, f.name); return; }
    if (f.size > (F.file_max_mb || 100) * 1048576) { toast(_t('Файл слишком большой')); return; }
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
  var circleBox = document.getElementById('circle-rec');
  var CANCEL_DX = -110, LOCK_DY = -70, HOLD_MS = 220;
  var LIMIT = { voice: 300, circle: 60 };

  function setMode(mode) {
    recBtn.dataset.mode = mode;
    recBtn.classList.remove('flip'); void recBtn.offsetWidth; recBtn.classList.add('flip');
  }
  function recUI(on) {
    form.classList.toggle('is-recording', on);
    if (!on) form.classList.remove('is-locked');
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
    R = { mode: mode, ready: false, cancelled: false, locked: !!locked, chunks: [] };
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
          var sec = (Date.now() - r.t0) / 1000;
          if (r.send && sec >= 1) upload(mode, new Blob(r.chunks, { type: r.mr.mimeType || mime }), sec);
          else if (r.send) toast(_t('Слишком коротко — удерживайте кнопку'));
        };
        if (!voice) {
          document.getElementById('circle-preview').srcObject = stream;
          circleBox.hidden = false; circleBox.classList.toggle('is-locked', r.locked);
        }
        r.t0 = Date.now(); r.ready = true; r.mr.start(250);
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
    var s = (Date.now() - r.t0) / 1000;
    recTime.textContent = mmss(s);
    if (r.mode === 'circle') {
      var ring = document.getElementById('circle-ring'), L = 2 * Math.PI * 48;
      ring.style.strokeDasharray = L; ring.style.strokeDashoffset = L * (1 - Math.min(s / 60, 1));
      document.getElementById('circle-time').textContent = mmss(s) + ' / 1:00';
    }
    if (s >= LIMIT[r.mode]) { finishRec(true); return; }
    requestAnimationFrame(function () { tickRec(r); });
  }
  function finishRec(send) {
    var r = R; if (!r) return;
    R = null; r.send = send; r.cancelled = !send;
    recUI(false);
    recSlide.style.transform = ''; recLock.style.transform = '';
    if (r.mr && r.mr.state !== 'inactive') r.mr.stop();
    else if (!r.ready && send) toast(_t('Удерживайте кнопку, чтобы записать'));
    if (r.mode === 'circle' && !r.mr) circleBox.hidden = true;
  }
  function lockRec() {
    if (!R || R.locked) return;
    R.locked = true; form.classList.add('is-locked'); circleBox.classList.add('is-locked');
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
  var cSend = document.getElementById('circle-send'), cCancel = document.getElementById('circle-cancel');
  if (cSend) cSend.addEventListener('click', function () { finishRec(true); });
  if (cCancel) cCancel.addEventListener('click', function () { finishRec(false); });

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
  log.addEventListener('click', function (e) {
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

  toBottom();
})();
