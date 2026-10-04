/* Фото профиля — как в Telegram: круг стоит на месте, а фото под ним двигают и приближают (пальцами, колесом мыши).
   Тут же: повернуть, отразить, порисовать, поправить цвет; можно сделать снимок камерой.
   Фото двигается средствами видеокарты (CSS transform), а не перерисовкой — поэтому плавно даже для больших снимков.
     ilm4Crop(file)        → Promise<File|null>  квадрат 640×640 под круг (null — отмена)
     ilm4PhotoSource(input) — «Сделать снимок / Выбрать фото» для поля с аватаром */
(function () {
  function T(s) { return window._t ? window._t(s) : s; }
  var I = {
    back: '<path d="M15 5l-7 7 7 7"/>', check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    rotate: '<path d="M4 9a8 8 0 1 1-1 5"/><path d="M4 4v5h5"/>',
    flip: '<path d="M12 3v18"/><path d="M8 7 4 12l4 5z"/><path d="M16 7l4 5-4 5z"/>',
    brush: '<path d="M18.4 3.6a2 2 0 0 1 2 2c0 1.1-6.2 8.2-8.6 10.4l-3-3C11 10.600 17.300 3.6 18.4 3.6z"/><path d="M8.800 13 6.5 13.600c-1.700.5-2.200 2.200-2.300 3.700 0 1-.5 1.900-1.200 2.500 2.500.7 6.800.3 7.900-2.300l.9-1.500"/>',
    tune: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2.200"/><circle cx="9" cy="17" r="2.200"/>',
    undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.500a5.500 5.500 0 0 1 0 11H11"/>',
    camera: '<path d="M4 8.500A2.500 2.500 0 0 1 6.500 6h1.200l1.200-1.800h6.200L16.300 6h1.200A2.500 2.500 0 0 1 20 8.500v8a2.500 2.500 0 0 1-2.500 2.500h-11A2.500 2.500 0 0 1 4 16.500z"/><circle cx="12" cy="12.500" r="3.400"/>',
    image: '<rect x="3.500" y="4.500" width="17" height="15" rx="3"/><circle cx="9" cy="10" r="1.700"/><path d="m4 17 5-4.500 4 3.500 3-2.500 4.500 3.500"/>'
  };
  function svg(n) { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + I[n] + '</svg>'; }
  var COLORS = ['#ffffff', '#111827', '#ef4444', '#f59e0b', '#22c55e', '#3b82f6', '#a855f7'];
  var ADJ = [['b', T('Яркость')], ['c', T('Контраст')], ['s', T('Насыщенность')], ['w', T('Теплота')], ['v', T('Виньетка')]];
  var OUT = 640;

  function crop(file) {
    return new Promise(function (done) {
      var img = new Image();
      img.onerror = function () { done(file); };
      img.onload = function () { build(img, file, done); };
      img.src = URL.createObjectURL(file);
    });
  }

  function build(img, file, done) {
    var st = { rot: 0, flip: false, s: 1, x: 0, y: 0, adj: { b: 0, c: 0, s: 0, w: 0, v: 0 }, strokes: [], mode: '', color: COLORS[2] };
    var box = document.createElement('div'); box.className = 'avc';
    box.innerHTML =
      '<button type="button" class="avc__back" data-a="cancel" aria-label="' + T('Отмена') + '">' + svg('back') + '</button>' +
      '<div class="avc__stage"><div class="avc__pic"><canvas class="avc__ink"></canvas></div><div class="avc__warm"></div><div class="avc__mask"></div></div>' +
      '<div class="avc__panel" hidden></div>' +
      '<div class="avc__bar"><div class="avc__tools">' +
        '<button type="button" data-a="rotate" aria-label="' + T('Повернуть') + '">' + svg('rotate') + '</button>' +
        '<button type="button" data-a="flip" aria-label="' + T('Отразить') + '">' + svg('flip') + '</button>' +
        '<button type="button" data-a="brush" aria-label="' + T('Рисовать') + '">' + svg('brush') + '</button>' +
        '<button type="button" data-a="tune" aria-label="' + T('Настройки цвета') + '">' + svg('tune') + '</button>' +
      '</div><button type="button" class="avc__ok" data-a="done" aria-label="' + T('Готово') + '">' + svg('check') + '</button></div>';
    document.body.appendChild(box);
    var stage = box.querySelector('.avc__stage'), pic = box.querySelector('.avc__pic'), ink = box.querySelector('.avc__ink'),
        mask = box.querySelector('.avc__mask'), warm = box.querySelector('.avc__warm'), panel = box.querySelector('.avc__panel'), bar = box.querySelector('.avc__bar');
    img.className = 'avc__img'; img.alt = ''; img.draggable = false; pic.insertBefore(img, ink);
    var D = 0, bw = 0, bh = 0, kq = 1;                 // диаметр круга; размер фото при масштабе 1 («покрыть круг»); во сколько раз холст рисунка крупнее

    function layout() {
      var r = stage.getBoundingClientRect();
      D = Math.max(160, Math.min(r.width - 28, r.height - 28, 460));
      var k = D / Math.min(img.naturalWidth, img.naturalHeight);
      bw = img.naturalWidth * k; bh = img.naturalHeight * k;
      pic.style.width = bw + 'px'; pic.style.height = bh + 'px'; pic.style.marginLeft = -bw / 2 + 'px'; pic.style.marginTop = -bh / 2 + 'px';
      mask.style.width = mask.style.height = warm.style.width = warm.style.height = D + 'px';
      if (!ink.width) { kq = Math.min(2, 1400 / Math.max(bw, bh)); ink.width = Math.round(bw * kq); ink.height = Math.round(bh * kq); }
      apply();
    }
    function ext() { return st.rot % 2 ? { w: bh * st.s, h: bw * st.s } : { w: bw * st.s, h: bh * st.s }; }
    function clamp() {
      st.s = Math.max(1, Math.min(6, st.s));
      var e = ext(), mx = Math.max(0, (e.w - D) / 2), my = Math.max(0, (e.h - D) / 2);
      st.x = Math.max(-mx, Math.min(mx, st.x)); st.y = Math.max(-my, Math.min(my, st.y));
    }
    function apply() {
      clamp();
      pic.style.transform = 'translate(' + st.x + 'px,' + st.y + 'px) scale(' + st.s + ') rotate(' + st.rot * 90 + 'deg) scaleX(' + (st.flip ? -1 : 1) + ')';
      var a = st.adj;
      img.style.filter = 'brightness(' + (1 + a.b * 0.5) + ') contrast(' + (1 + a.c * 0.6) + ') saturate(' + (1 + a.s) + ')';
      warm.style.background = a.w >= 0 ? 'rgb(255,150,40)' : 'rgb(50,130,255)'; warm.style.opacity = Math.abs(a.w) * 0.45;
      mask.style.setProperty('--vig', a.v * 0.8);
    }
    function zoomAt(px, py, f) {                         // приблизить к точке (px, py — от центра круга)
      var s0 = st.s; st.s = Math.max(1, Math.min(6, st.s * f)); var k = st.s / s0;
      st.x = px - (px - st.x) * k; st.y = py - (py - st.y) * k; apply();
    }
    function center(e) { var r = stage.getBoundingClientRect(); return [e.clientX - r.left - r.width / 2, e.clientY - r.top - r.height / 2]; }
    function local(e) {                                   // точка экрана → точка на фото (для рисования)
      var p = center(e), vx = (p[0] - st.x) / st.s, vy = (p[1] - st.y) / st.s, a = -st.rot * Math.PI / 2;
      var x = vx * Math.cos(a) - vy * Math.sin(a), y = vx * Math.sin(a) + vy * Math.cos(a);
      if (st.flip) x = -x;
      return [(x + bw / 2) * kq, (y + bh / 2) * kq];
    }
    function redraw() {
      var c = ink.getContext('2d'); c.clearRect(0, 0, ink.width, ink.height); c.lineCap = c.lineJoin = 'round';
      st.strokes.forEach(function (o) {
        c.strokeStyle = o.color; c.lineWidth = o.w; c.beginPath();
        o.pts.forEach(function (p, i) { if (i) c.lineTo(p[0], p[1]); else c.moveTo(p[0], p[1]); });
        if (o.pts.length === 1) c.lineTo(o.pts[0][0] + 0.1, o.pts[0][1]);
        c.stroke();
      });
    }

    /* ---------- жесты: один палец — двигать, два — приближать; в режиме кисти — рисовать ---------- */
    var pts = {}, pinch = null, stroke = null;
    stage.addEventListener('pointerdown', function (e) {
      e.preventDefault(); stage.setPointerCapture(e.pointerId);
      pts[e.pointerId] = center(e);
      var ids = Object.keys(pts);
      if (st.mode === 'brush' && ids.length === 1) { stroke = { color: st.color, w: Math.max(3, 7 * kq / st.s), pts: [local(e)] }; st.strokes.push(stroke); redraw(); return; }
      if (ids.length === 2) {
        if (stroke) { st.strokes.pop(); stroke = null; redraw(); }
        var a = pts[ids[0]], b = pts[ids[1]]; pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1 };
      }
    });
    stage.addEventListener('pointermove', function (e) {
      if (!pts[e.pointerId]) return;
      var prev = pts[e.pointerId], cur = center(e); pts[e.pointerId] = cur;
      var ids = Object.keys(pts);
      if (stroke && ids.length === 1) { stroke.pts.push(local(e)); redraw(); return; }
      if (ids.length >= 2 && pinch) {
        var a = pts[ids[0]], b = pts[ids[1]], d = Math.hypot(a[0] - b[0], a[1] - b[1]) || 1;
        zoomAt((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, d / pinch.d); pinch.d = d; return;
      }
      st.x += cur[0] - prev[0]; st.y += cur[1] - prev[1]; apply();
    });
    function up(e) { delete pts[e.pointerId]; if (Object.keys(pts).length < 2) pinch = null; stroke = null; }
    stage.addEventListener('pointerup', up); stage.addEventListener('pointercancel', up);
    stage.addEventListener('wheel', function (e) { e.preventDefault(); var p = center(e); zoomAt(p[0], p[1], e.deltaY < 0 ? 1.12 : 1 / 1.12); }, { passive: false });
    stage.addEventListener('dblclick', function (e) { if (st.mode === 'brush') return; var p = center(e); zoomAt(p[0], p[1], st.s > 1.6 ? 1 / st.s : 2); });

    /* ---------- панели: цвет (список ползунков, как в Telegram) и кисть ---------- */
    function showPanel(mode) {
      st.mode = mode; box.classList.toggle('avc--brush', mode === 'brush');
      bar.hidden = !!mode; panel.hidden = !mode;
      if (!mode) { panel.innerHTML = ''; return; }
      if (mode === 'tune') {
        var keep = JSON.stringify(st.adj);
        panel.innerHTML = '<div class="avc__sliders">' + ADJ.map(function (a) {
          var min = a[0] === 'v' ? 0 : -100, v = Math.round(st.adj[a[0]] * 100);
          return '<label class="avc__sl"><span><b>' + a[1] + '</b><output' + (v ? ' class="on"' : '') + '>' + v + '</output></span><input type="range" min="' + min + '" max="100" value="' + v + '" data-k="' + a[0] + '"></label>';
        }).join('') + '</div><div class="avc__pf"><button type="button" data-p="cancel">' + T('Отмена') + '</button><button type="button" data-p="ok">' + T('Готово') + '</button></div>';
        panel.dataset.keep = keep;
      } else {
        panel.innerHTML = '<div class="avc__colors">' + COLORS.map(function (c) { return '<button type="button" data-c="' + c + '" style="background:' + c + '"' + (c === st.color ? ' class="on"' : '') + '></button>'; }).join('') +
          '<button type="button" class="avc__undo" data-p="undo" aria-label="' + T('Отменить шаг') + '">' + svg('undo') + '</button></div>' +
          '<div class="avc__pf"><span>' + T('Рисуйте пальцем по фото') + '</span><button type="button" data-p="ok">' + T('Готово') + '</button></div>';
      }
    }
    panel.addEventListener('input', function (e) {
      var k = e.target.dataset && e.target.dataset.k; if (!k) return;
      st.adj[k] = parseInt(e.target.value, 10) / 100;
      var out = e.target.parentNode.querySelector('output'); out.textContent = e.target.value; out.classList.toggle('on', e.target.value !== '0');
      apply();
    });
    panel.addEventListener('click', function (e) {
      var c = e.target.closest('[data-c]');
      if (c) { st.color = c.dataset.c; panel.querySelectorAll('[data-c]').forEach(function (x) { x.classList.toggle('on', x === c); }); return; }
      var b = e.target.closest('[data-p]'); if (!b) return;
      if (b.dataset.p === 'undo') { st.strokes.pop(); redraw(); return; }
      if (b.dataset.p === 'cancel' && panel.dataset.keep) { st.adj = JSON.parse(panel.dataset.keep); apply(); }
      showPanel('');
    });

    /* ---------- готовое фото: тот же кадр, что в круге, 640×640 ---------- */
    function result() {
      var cv = document.createElement('canvas'); cv.width = cv.height = OUT;
      var x = cv.getContext('2d'), q = OUT / D;
      function place() { x.setTransform(1, 0, 0, 1, 0, 0); x.translate(OUT / 2, OUT / 2); x.scale(q, q); x.translate(st.x, st.y); x.scale(st.s, st.s); x.rotate(st.rot * Math.PI / 2); if (st.flip) x.scale(-1, 1); }
      x.fillStyle = '#000'; x.fillRect(0, 0, OUT, OUT);
      place(); x.drawImage(img, -bw / 2, -bh / 2, bw, bh);
      var a = st.adj;
      if (a.b || a.c || a.s) {                           // те же формулы, что у CSS-фильтров в окне — результат совпадает с тем, что видно
        x.setTransform(1, 0, 0, 1, 0, 0);
        var id = x.getImageData(0, 0, OUT, OUT), p = id.data, B = 1 + a.b * 0.5, C = 1 + a.c * 0.6, S = 1 + a.s;
        for (var i = 0; i < p.length; i += 4) {
          var r = p[i] * B, g = p[i + 1] * B, b = p[i + 2] * B;
          r = (r - 127.5) * C + 127.5; g = (g - 127.5) * C + 127.5; b = (b - 127.5) * C + 127.5;
          var r2 = (0.213 + 0.787 * S) * r + (0.715 - 0.715 * S) * g + (0.072 - 0.072 * S) * b;
          var g2 = (0.213 - 0.213 * S) * r + (0.715 + 0.285 * S) * g + (0.072 - 0.072 * S) * b;
          var b2 = (0.213 - 0.213 * S) * r + (0.715 - 0.715 * S) * g + (0.072 + 0.928 * S) * b;
          p[i] = r2; p[i + 1] = g2; p[i + 2] = b2;
        }
        x.putImageData(id, 0, 0);
      }
      if (st.strokes.length) { place(); x.drawImage(ink, -bw / 2, -bh / 2, bw, bh); }
      x.setTransform(1, 0, 0, 1, 0, 0);
      if (a.w) { x.globalCompositeOperation = 'soft-light'; x.globalAlpha = Math.abs(a.w) * 0.45; x.fillStyle = a.w >= 0 ? 'rgb(255,150,40)' : 'rgb(50,130,255)'; x.fillRect(0, 0, OUT, OUT); x.globalAlpha = 1; x.globalCompositeOperation = 'source-over'; }
      if (a.v > 0) { var g0 = x.createRadialGradient(OUT / 2, OUT / 2, OUT * 0.3, OUT / 2, OUT / 2, OUT * 0.72); g0.addColorStop(0, 'rgba(0,0,0,0)'); g0.addColorStop(1, 'rgba(0,0,0,' + a.v * 0.8 + ')'); x.fillStyle = g0; x.fillRect(0, 0, OUT, OUT); }
      return cv;
    }
    function close(value) { window.removeEventListener('resize', layout); document.removeEventListener('keydown', onKey); URL.revokeObjectURL(img.src); box.remove(); done(value); }
    function onKey(e) { if (e.key === 'Escape') { if (st.mode) showPanel(''); else close(null); } }
    box.addEventListener('click', function (e) {
      var b = e.target.closest('[data-a]'); if (!b) return;
      var a = b.dataset.a;
      if (a === 'cancel') close(null);
      else if (a === 'rotate') { st.rot = (st.rot + 3) % 4; var t = st.x; st.x = st.y; st.y = -t; apply(); }
      else if (a === 'flip') { st.flip = !st.flip; if (st.rot % 2) st.rot = (st.rot + 2) % 4; st.x = -st.x; apply(); }   // всегда «зеркало» слева направо на экране
      else if (a === 'brush' || a === 'tune') showPanel(a);
      else if (a === 'done') {
        b.disabled = true;
        result().toBlob(function (blob) { close(new File([blob], (file.name || 'photo').replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' })); }, 'image/jpeg', 0.92);
      }
    });
    window.addEventListener('resize', layout); document.addEventListener('keydown', onKey);
    layout();
  }
  window.ilm4Crop = crop;

  /* ---------- «Сделать снимок / Выбрать фото» ---------- */
  function give(input, file) {                              // положить готовое фото в поле формы, как будто его выбрали
    if (!file || !window.DataTransfer) return;
    var dt = new DataTransfer(); dt.items.add(file); input.files = dt.files;
    input.dataset.cropped = '1'; input.dispatchEvent(new Event('change', { bubbles: true })); delete input.dataset.cropped;
  }
  function webcam() {                                       // на компьютере — окно с камерой и кнопкой снимка
    return new Promise(function (ok) {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { ok(null); return; }
      navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false }).then(function (stream) {
        var box = document.createElement('div'); box.className = 'avc avc--cam';
        box.innerHTML = '<button type="button" class="avc__back" data-a="cancel" aria-label="' + T('Отмена') + '">' + svg('back') + '</button>' +
          '<div class="avc__stage"><video autoplay playsinline muted></video></div><div class="avc__bar avc__bar--cam"><button type="button" class="avc__shot" data-a="shot" aria-label="' + T('Сделать снимок') + '"></button></div>';
        document.body.appendChild(box);
        var video = box.querySelector('video'); video.srcObject = stream;
        function end(v) { stream.getTracks().forEach(function (t) { t.stop(); }); box.remove(); ok(v); }
        box.addEventListener('click', function (e) {
          var b = e.target.closest('[data-a]'); if (!b) return;
          if (b.dataset.a === 'cancel') { end(null); return; }
          var cv = document.createElement('canvas'); cv.width = video.videoWidth; cv.height = video.videoHeight;
          var x = cv.getContext('2d'); x.translate(cv.width, 0); x.scale(-1, 1); x.drawImage(video, 0, 0);     // как в зеркале — как человек видел себя в окне
          cv.toBlob(function (blob) { end(blob ? new File([blob], 'camera.jpg', { type: 'image/jpeg' }) : null); }, 'image/jpeg', 0.92);
        });
      }).catch(function () { if (window.tgToast) window.tgToast(T('Камера недоступна — выберите фото из файлов')); ok(null); });
    });
  }
  function source(input) {
    var touch = window.matchMedia && window.matchMedia('(pointer:coarse)').matches;
    var sheet = document.createElement('div'); sheet.className = 'sxs';
    sheet.innerHTML = '<div class="sxs__p"><div class="sxs__grip"></div><div class="sxs__l">' +
      '<button type="button" class="sxs__i sxs__i--act" data-s="camera">' + svg('camera') + '<span>' + T('Сделать снимок') + '</span></button>' +
      '<button type="button" class="sxs__i sxs__i--act" data-s="file">' + svg('image') + '<span>' + T('Выбрать фото') + '</span></button></div></div>';
    document.body.appendChild(sheet);
    sheet.addEventListener('click', function (e) {
      var b = e.target.closest('[data-s]');
      if (!b && e.target !== sheet) return;
      sheet.remove();
      if (!b) return;
      if (b.dataset.s === 'file') { input.click(); return; }
      if (touch) {                                            // телефон: системная камера
        var cam = document.createElement('input'); cam.type = 'file'; cam.accept = 'image/*'; cam.setAttribute('capture', 'user');
        cam.addEventListener('change', function () { if (cam.files[0]) crop(cam.files[0]).then(function (f) { give(input, f); }); });
        cam.click(); return;
      }
      webcam().then(function (shot) { if (shot) crop(shot).then(function (f) { give(input, f); }); });
    });
  }
  window.ilm4PhotoSource = source;
  // нажали на «поставить фото» (аватар профиля, группы, канала, сообщества) — сначала спрашиваем: снимок или файл
  document.addEventListener('click', function (e) {
    var lab = e.target.closest('label[for]'); if (!lab) return;
    var input = document.getElementById(lab.getAttribute('for'));
    if (!input || !input.matches('input[type=file][data-crop], #id_avatar')) return;
    e.preventDefault(); source(input);
  });
})();
