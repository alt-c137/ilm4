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
  function toBottom() { log.scrollTop = log.scrollHeight; }
  function toast(text) {
    var t = document.createElement('div'); t.className = 'tg__toast'; t.textContent = text;
    document.body.appendChild(t); setTimeout(function () { t.remove(); }, 3500);
  }
  var ICON = {
    play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M8 5.5v13l11-6.5z"/></svg>',
    pause: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M9 5.5v13M15 5.5v13"/></svg>',
    call: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 3.5h3l1.5 4-2 1.5a12 12 0 0 0 6 6l1.5-2 4 1.5v3a2 2 0 0 1-2.2 2A16.5 16.5 0 0 1 4.5 5.7 2 2 0 0 1 6.5 3.5z"/></svg>'
  };

  /* ---------- вывод сообщений ---------- */
  function lastDay() { var d = log.querySelectorAll('.tg__day'); return d.length ? d[d.length - 1].dataset.day : ''; }
  function msgHTML(d, mine) {
    if (d.kind === 'system') return '<div class="tg__sys" data-id="' + d.id + '"><span>' + ICON.call + esc(d.body) + ' · ' + esc(d.time) + '</span></div>';
    var media = '';
    if (d.kind === 'photo') media = '<a class="bub__photo" href="' + d.url + '" target="_blank" rel="noopener"><img src="' + d.url + '" alt="Фото"></a>';
    if (d.kind === 'voice') media = '<div class="voice" data-src="' + d.url + '"><button type="button" class="voice__play" aria-label="Слушать">' + ICON.play + '</button><span class="voice__bar"><i></i></span><span class="voice__t">' + mmss(d.duration) + '</span></div>';
    if (d.kind === 'circle') media = '<div class="circle" data-src="' + d.url + '"><video src="' + d.url + '" preload="metadata" playsinline></video><span class="circle__t">' + mmss(d.duration) + '</span><span class="circle__play">' + ICON.play + '</span></div>';
    return '<div class="bub bub--' + d.kind + (mine ? ' bub--me' : '') + ' bub--tail" data-id="' + d.id + '">' + media +
      (d.body ? '<span class="bub__t">' + esc(d.body) + '</span>' : '') +
      '<span class="bub__meta">' + esc(d.time || '') + (mine ? '<span class="tick"></span>' : '') + '</span></div>';
  }
  function add(d) {
    if (seen[d.id]) return;
    seen[d.id] = 1;
    var em = document.getElementById('chat-empty'); if (em) em.remove();
    if (d.day && d.day !== lastDay()) {
      var day = document.createElement('div'); day.className = 'tg__day'; day.dataset.day = d.day;
      day.innerHTML = '<span>Сегодня</span>'; log.appendChild(day);
    }
    var mine = d.sender_id === cfg.me;
    var prev = log.lastElementChild;
    if (prev && prev.classList.contains('bub') && prev.classList.contains('bub--me') === mine) prev.classList.remove('bub--tail');
    log.insertAdjacentHTML('beforeend', msgHTML(d, mine));
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

  /* ---------- текст ---------- */
  var micBtn = document.getElementById('mic-btn'), sendBtn = document.getElementById('send-btn');
  function syncButtons() {
    if (!micBtn) return;
    var empty = !input.value.trim();
    micBtn.hidden = !empty; sendBtn.hidden = empty;
  }
  function grow() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 140) + 'px'; }
  function sendText() {
    var v = input.value.trim();
    if (!v) return false;
    if (!(sock && sock.readyState === 1)) return false;   // запасной путь — обычная отправка формы
    wsSend({ body: v }); input.value = ''; grow(); syncButtons();
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
  syncButtons();

  /* ---------- загрузка вложений ---------- */
  function upload(kind, blob, duration, name) {
    var fd = new FormData();
    fd.append('kind', kind); fd.append('file', blob, name || kind);
    if (duration) fd.append('duration', String(Math.round(duration)));
    var bar = document.createElement('div'); bar.className = 'tg__uploading'; bar.textContent = 'Отправка…';
    log.appendChild(bar); toBottom();
    return fetch('/chat/' + cfg.thread + '/upload/', { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-CSRFToken': csrf } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) { bar.remove(); if (!res.ok) { toast(res.j.error || 'Не удалось отправить'); return; } add(res.j); })
      .catch(function () { bar.remove(); toast('Нет соединения — попробуйте ещё раз'); });
  }
  var photoInput = document.getElementById('photo-input');
  if (photoInput) photoInput.addEventListener('change', function () {
    if (photoInput.files[0]) upload('photo', photoInput.files[0], 0, photoInput.files[0].name);
    photoInput.value = '';
  });

  function pickMime(list) {
    if (!window.MediaRecorder) return null;
    for (var i = 0; i < list.length; i++) if (MediaRecorder.isTypeSupported(list[i])) return list[i];
    return '';
  }

  /* ---------- голосовое ---------- */
  var rec = null;
  var recBar = document.getElementById('rec-bar');
  function stopTracks(stream) { if (stream) stream.getTracks().forEach(function (t) { t.stop(); }); }
  function startVoice() {
    var mime = pickMime(['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']);
    if (mime === null || !navigator.mediaDevices) { toast('Запись голоса не поддерживается в этом браузере'); return; }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      var chunks = [], mr = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined), t0 = Date.now();
      mr.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
      rec = { mr: mr, stream: stream, chunks: chunks, t0: t0, send: false };
      mr.onstop = function () {
        stopTracks(stream);
        var sec = (Date.now() - t0) / 1000;
        if (rec && rec.send && sec >= 1) upload('voice', new Blob(chunks, { type: mr.mimeType || mime }), sec);
        rec = null; recBar.hidden = true; form.hidden = false;
      };
      mr.start(250);
      form.hidden = true; recBar.hidden = false;
      var timeEl = document.getElementById('rec-time');
      (function tick() {
        if (!rec) return;
        var s = (Date.now() - t0) / 1000; timeEl.textContent = mmss(s);
        if (s >= 300) { rec.send = true; mr.stop(); return; }
        setTimeout(tick, 250);
      })();
    }).catch(function () { toast('Нет доступа к микрофону — разрешите его в настройках браузера'); });
  }
  if (micBtn) micBtn.addEventListener('click', startVoice);
  var recSend = document.getElementById('rec-send'), recCancel = document.getElementById('rec-cancel');
  if (recSend) recSend.addEventListener('click', function () { if (rec) { rec.send = true; rec.mr.stop(); } });
  if (recCancel) recCancel.addEventListener('click', function () { if (rec) { rec.send = false; rec.mr.stop(); } });

  /* ---------- видеокружок ---------- */
  var circleBtn = document.getElementById('circle-btn'), crec = null;
  var circleBox = document.getElementById('circle-rec');
  function startCircle() {
    var mime = pickMime(['video/mp4;codecs=avc1,mp4a', 'video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm']);
    if (mime === null || !navigator.mediaDevices) { toast('Видеозапись не поддерживается в этом браузере'); return; }
    navigator.mediaDevices.getUserMedia({ audio: true, video: { facingMode: 'user', width: { ideal: 480 }, height: { ideal: 480 } } }).then(function (stream) {
      var prev = document.getElementById('circle-preview'); prev.srcObject = stream;
      var chunks = [], mr = new MediaRecorder(stream, mime ? { mimeType: mime, videoBitsPerSecond: 900000 } : undefined), t0 = Date.now();
      mr.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
      crec = { mr: mr, send: false };
      mr.onstop = function () {
        stopTracks(stream); prev.srcObject = null; circleBox.hidden = true;
        var sec = (Date.now() - t0) / 1000;
        if (crec && crec.send && sec >= 1) upload('circle', new Blob(chunks, { type: mr.mimeType || mime }), sec);
        crec = null;
      };
      mr.start(250); circleBox.hidden = false;
      var ring = document.getElementById('circle-ring'), tEl = document.getElementById('circle-time'), L = 2 * Math.PI * 48;
      ring.style.strokeDasharray = L;
      (function tick() {
        if (!crec) return;
        var s = (Date.now() - t0) / 1000;
        ring.style.strokeDashoffset = L * (1 - Math.min(s / 60, 1));
        tEl.textContent = mmss(s) + ' / 1:00';
        if (s >= 60) { crec.send = true; mr.stop(); return; }
        requestAnimationFrame(tick);
      })();
    }).catch(function () { toast('Нет доступа к камере или микрофону'); });
  }
  if (circleBtn) circleBtn.addEventListener('click', startCircle);
  var cSend = document.getElementById('circle-send'), cCancel = document.getElementById('circle-cancel');
  if (cSend) cSend.addEventListener('click', function () { if (crec) { crec.send = true; crec.mr.stop(); } });
  if (cCancel) cCancel.addEventListener('click', function () { if (crec) { crec.send = false; crec.mr.stop(); } });

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
        if (pc.connectionState === 'connected' && !c.start) { c.start = Date.now(); tick(); }
        if (pc.connectionState === 'failed') { toast('Не удалось соединиться. Возможно, нужна настройка TURN-сервера.'); finish(true); }
      };
      c.pc = pc;
      return pc;
    }
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
      if (!window.RTCPeerConnection || !navigator.mediaDevices) { toast('Звонки не поддерживаются в этом браузере'); return; }
      c = { role: 'caller', video: video, pendingIce: [] };
      ui('ringing', 'Доступ к ' + (video ? 'камере…' : 'микрофону…'));
      media(video).then(function (stream) {
        if (!c) { stopTracks(stream); return; }
        c.local = stream; if (video) localV.srcObject = stream;
        ui('ringing', 'Звоним…');
        var ring = function () { wsSend({ type: 'signal', action: 'ring', video: video }); };
        ring(); c.ringT = setInterval(ring, 3000);   // повтор: собеседник мог открыть страницу позже
        c.timeoutT = setTimeout(function () { finish(true, 'missed'); toast('Не отвечает'); }, 45000);
      }).catch(function () { cleanup(); toast('Нет доступа к ' + (video ? 'камере' : 'микрофону')); });
    }
    function accept() {
      if (!c || c.role !== 'callee') return;
      ui('connecting', 'Соединение…');
      media(c.video).then(function (stream) {
        if (!c) { stopTracks(stream); return; }
        c.local = stream; if (c.video) localV.srcObject = stream;
        wsSend({ type: 'signal', action: 'accept' });
      }).catch(function () { toast('Нет доступа к ' + (c.video ? 'камере' : 'микрофону')); decline(); });
    }
    function decline() { if (!c) return; wsSend({ type: 'signal', action: 'decline' }); cleanup(); }

    function onSignal(d) {
      var a = d.action;
      if (a === 'ring') {
        if (c) return;                       // уже в звонке / повтор сигнала
        c = { role: 'callee', video: !!d.video, pendingIce: [] };
        ui('incoming', (d.video ? 'Видеозвонок' : 'Аудиозвонок') + ' · входящий');
        if (autoAnswer) { autoAnswer = false; accept(); }
        return;
      }
      if (!c) return;
      if (a === 'accept' && c.role === 'caller' && !c.pc) {
        clearInterval(c.ringT); clearTimeout(c.timeoutT);
        ui('connecting', 'Соединение…');
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
        toast('Звонок отклонён'); finish(false, 'declined');
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
