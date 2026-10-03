/* Голосовая комната сообщества. Звук идёт напрямую между участниками (WebRTC, каждый с каждым) — сервер только
   знакомит их (apps/chat/voice.py). Новый участник сам звонит всем, кто уже в комнате; ответы приходят обратно. */
(function () {
  var root = document.getElementById('vc'); if (!root) return;
  var T = function (s) { return window._t ? window._t(s) : s; };
  var IC = {}; try { IC = JSON.parse(document.getElementById('ui-icons').textContent); } catch (e) { /* без значков */ }
  var grid = document.getElementById('vc-grid'), stateEl = document.getElementById('vc-state'), audioBox = document.getElementById('vc-audio');
  var bJoin = document.getElementById('vc-join'), bMute = document.getElementById('vc-mute'), bLeave = document.getElementById('vc-leave');
  var ws = null, stream = null, me = null, ice = [], peers = {}, muted = false, pingT = 0, levelT = 0, ctxAudio = null;

  function esc(x) { var d = document.createElement('div'); d.textContent = x == null ? '' : x; return d.innerHTML; }
  function tile(p) {
    var el = document.createElement('div'); el.className = 'vc__tile'; el.dataset.peer = p.peer;
    el.innerHTML = (p.avatar ? '<img src="' + esc(p.avatar) + '" alt="">' : '<span>' + esc((p.name || '?').slice(0, 1).toUpperCase()) + '</span>') +
      '<b>' + esc(p.name) + '</b><i class="vc__mic"' + (p.muted ? '' : ' hidden') + '>' + (IC.micoff || '') + '</i>';
    grid.appendChild(el); return el;
  }
  function drop(peer) {
    var p = peers[peer]; if (!p) return;
    if (p.pc) p.pc.close();
    if (p.audio) p.audio.remove();
    if (p.el) p.el.remove();
    delete peers[peer]; count();
  }
  function count() { var n = Object.keys(peers).length + (me ? 1 : 0); stateEl.textContent = me ? T('В комнате:') + ' ' + n : stateEl.textContent; }
  function send(o) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(o)); }

  function connect(info, initiator) {
    var pc = new RTCPeerConnection({ iceServers: ice });
    var p = peers[info.peer] = { pc: pc, el: tile(info), audio: null };
    stream.getTracks().forEach(function (t) { pc.addTrack(t, stream); });
    pc.onicecandidate = function (e) { if (e.candidate) send({ type: 'signal', to: info.peer, data: { candidate: e.candidate } }); };
    pc.ontrack = function (e) {
      if (!p.audio) { p.audio = document.createElement('audio'); p.audio.autoplay = true; audioBox.appendChild(p.audio); }
      p.audio.srcObject = e.streams[0];
    };
    pc.onconnectionstatechange = function () { p.el.classList.toggle('is-on', pc.connectionState === 'connected'); if (pc.connectionState === 'failed') drop(info.peer); };
    if (initiator) pc.createOffer().then(function (o) { return pc.setLocalDescription(o); }).then(function () { send({ type: 'signal', to: info.peer, data: { sdp: pc.localDescription } }); });
    count();
    return p;
  }
  function onSignal(from, data) {
    var p = peers[from]; if (!p) return;
    if (data.sdp) {
      p.pc.setRemoteDescription(data.sdp).then(function () {
        if (data.sdp.type === 'offer') return p.pc.createAnswer().then(function (a) { return p.pc.setLocalDescription(a); }).then(function () { send({ type: 'signal', to: from, data: { sdp: p.pc.localDescription } }); });
      }).catch(function () { /* повторный сигнал — пропускаем */ });
    } else if (data.candidate) p.pc.addIceCandidate(data.candidate).catch(function () {});
  }
  function leave(text) {
    clearInterval(pingT); clearInterval(levelT);
    Object.keys(peers).forEach(drop);
    if (ws) { ws.onclose = null; ws.close(); ws = null; }
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
    if (ctxAudio) { ctxAudio.close(); ctxAudio = null; }
    grid.innerHTML = ''; me = null;
    bJoin.hidden = false; bMute.hidden = bLeave.hidden = true;
    stateEl.textContent = text || T('Вы вышли из комнаты.');
  }
  function speaking() {                                   // рамка у своей плитки, когда говоришь (громкость микрофона)
    try {
      ctxAudio = new (window.AudioContext || window.webkitAudioContext)();
      var an = ctxAudio.createAnalyser(); an.fftSize = 256; ctxAudio.createMediaStreamSource(stream).connect(an);
      var buf = new Uint8Array(an.frequencyBinCount);
      levelT = setInterval(function () {
        an.getByteFrequencyData(buf); var s = 0; for (var i = 0; i < buf.length; i++) s += buf[i];
        var mine = grid.querySelector('[data-peer="' + me + '"]'); if (mine) mine.classList.toggle('is-talk', !muted && s / buf.length > 18);
      }, 200);
    } catch (e) { /* без индикатора */ }
  }
  bJoin.addEventListener('click', function () {
    bJoin.disabled = true;
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } }).then(function (s) {
      stream = s; muted = false;
      ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + root.dataset.ws);
      ws.onmessage = function (e) {
        var d = JSON.parse(e.data);
        if (d.type === 'hello') {
          me = d.me; ice = d.ice || [];
          var mine = tile({ peer: me, name: T('Вы'), avatar: '', muted: false }); mine.classList.add('is-on', 'is-me');
          d.peers.forEach(function (p) { connect(p, true); });
          bJoin.hidden = true; bJoin.disabled = false; bMute.hidden = bLeave.hidden = false; count(); speaking();
          pingT = setInterval(function () { send({ type: 'ping' }); }, 25000);
        } else if (d.type === 'full') { leave(T('В комнате уже максимум участников.')); bJoin.disabled = false; }
        else if (d.type === 'joined') connect(d, false);
        else if (d.type === 'left') drop(d.peer);
        else if (d.type === 'signal') onSignal(d.from, d.data);
        else if (d.type === 'state') { var p = peers[d.peer], el = p ? p.el : grid.querySelector('[data-peer="' + d.peer + '"]'); if (el) el.querySelector('.vc__mic').hidden = !d.muted; }
      };
      ws.onclose = function () { leave(T('Связь с комнатой прервалась.')); bJoin.disabled = false; };
    }).catch(function () { bJoin.disabled = false; stateEl.textContent = T('Нет доступа к микрофону — разрешите его в настройках браузера.'); });
  });
  bMute.addEventListener('click', function () {
    muted = !muted;
    if (stream) stream.getAudioTracks().forEach(function (t) { t.enabled = !muted; });
    bMute.classList.toggle('is-off', muted); bMute.innerHTML = muted ? (IC.micoff || '') : (IC.mic || '');
    var mine = grid.querySelector('[data-peer="' + me + '"] .vc__mic'); if (mine) mine.hidden = !muted;
    send({ type: 'state', muted: muted });
  });
  bLeave.addEventListener('click', function () { leave(); });
  window.addEventListener('pagehide', function () { if (ws) ws.close(); });
  window.ilm4Voice = { peers: peers };                    // для проверки соединения в тестах
})();
