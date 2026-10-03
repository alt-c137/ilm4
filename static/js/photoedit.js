/* Редактор фото — по образцу Telegram: кадр (рамка, пропорции, поворот, отражение), цвет (яркость, контраст,
   насыщенность, теплота, выцветание, виньетка), рисунок (карандаш, маркер, стрелка), текст. Всё на canvas, без библиотек.
     ilm4PhotoEdit(file) → Promise<File|null>   фото перед отправкой в чат (null — отмена)
     ilm4Crop(file)      → Promise<File|null>   аватар: квадрат с кругом-подсказкой, на выходе 640×640
   Значки — из набора Lucide (ISC License). */
(function () {
  var IC = {"close": "<path d=\"M6 6l12 12M18 6 6 18\"/>", "undo": "<path d=\"M9 14 4 9l5-5\"/><path d=\"M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11\"/>", "crop": "<path d=\"M6 2v14a2 2 0 0 0 2 2h14\"/><path d=\"M18 22V8a2 2 0 0 0-2-2H2\"/>", "adjust": "<path d=\"M10 5H3\"/><path d=\"M12 19H3\"/><path d=\"M14 3v4\"/><path d=\"M16 17v4\"/><path d=\"M21 12h-9\"/><path d=\"M21 19h-5\"/><path d=\"M21 5h-7\"/><path d=\"M8 10v4\"/><path d=\"M8 12H3\"/>", "pencil": "<path d=\"M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z\"/><path d=\"m15 5 4 4\"/>", "type": "<path d=\"M12 4v16\"/><path d=\"M4 7V5a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v2\"/><path d=\"M9 20h6\"/>", "rotate": "<path d=\"M20 9V7a2 2 0 0 0-2-2h-6\"/><path d=\"m15 2-3 3 3 3\"/><path d=\"M20 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2\"/>", "flip": "<path d=\"M10 12H8\"/><path d=\"M16 12h-2\"/><path d=\"M22 12h-2\"/><path d=\"M4 12H2\"/><path d=\"M7.298 20.288A1 1 0 008 22h8a1 1 0 00.703-1.712l-3.991-3.99a1 1 0 00-1.424-.001z\"/><path d=\"M7.298 3.712A1 1 0 018 2h8a1 1 0 01.703 1.712l-3.991 3.99a1 1 0 01-1.424.001z\"/>", "wand": "<path d=\"m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72\"/><path d=\"m14 7 3 3\"/><path d=\"M5 6v4\"/><path d=\"M19 14v4\"/><path d=\"M10 2v2\"/><path d=\"M7 8H3\"/><path d=\"M21 16h-4\"/><path d=\"M11 3H9\"/>", "marker": "<path d=\"m9 11-6 6v3h9l3-3\"/><path d=\"m22 12-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4\"/>", "arrow": "<path d=\"M5 12h14M13 6l6 6-6 6\"/>", "bright": "<circle cx=\"12\" cy=\"12\" r=\"4\"/><path d=\"M12 3v1\"/><path d=\"M12 20v1\"/><path d=\"M3 12h1\"/><path d=\"M20 12h1\"/><path d=\"m18.364 5.636-.707.707\"/><path d=\"m6.343 17.657-.707.707\"/><path d=\"m5.636 5.636.707.707\"/><path d=\"m17.657 17.657.707.707\"/>", "contrast": "<circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"M12 18a6 6 0 0 0 0-12v12z\"/>", "saturation": "<path d=\"M7 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S7.29 6.75 7 5.3c-.29 1.45-1.14 2.84-2.29 3.76S3 11.1 3 12.25c0 2.22 1.8 4.05 4 4.05z\"/><path d=\"M12.56 6.6A10.97 10.97 0 0 0 14 3.02c.5 2.5 2 4.9 4 6.5s3 3.5 3 5.5a6.98 6.98 0 0 1-11.91 4.97\"/>", "warmth": "<path d=\"M12 2v2\"/><path d=\"M12 8a4 4 0 0 0-1.645 7.647\"/><path d=\"M2 12h2\"/><path d=\"M20 14.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0z\"/><path d=\"m4.93 4.93 1.41 1.41\"/><path d=\"m6.34 17.66-1.41 1.41\"/>", "fade": "<circle cx=\"15\" cy=\"9\" r=\"7\"/><circle cx=\"9\" cy=\"15\" r=\"7\"/>", "vignette": "<circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"m14.31 8 5.74 9.94\"/><path d=\"M9.69 8h11.48\"/><path d=\"m7.38 12 5.74-9.94\"/><path d=\"M9.69 16 3.95 6.06\"/><path d=\"M14.31 16H2.83\"/><path d=\"m16.62 12-5.74 9.94\"/>"};
  function T(s) { return window._t ? window._t(s) : s; }
  function svg(n) { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (IC[n] || '') + '</svg>'; }
  var COLORS = ['#ffffff', '#111827', '#ef4444', '#f59e0b', '#22c55e', '#3b82f6', '#a855f7'];
  var MAX = 2048, PREVIEW = 1100;
  var ADJ = [['b', T('Яркость'), 'bright'], ['c', T('Контраст'), 'contrast'], ['s', T('Насыщенность'), 'saturation'],
             ['w', T('Теплота'), 'warmth'], ['f', T('Выцветание'), 'fade'], ['v', T('Виньетка'), 'vignette']];
  var ASPECTS = [[0, T('Свободно')], [-1, T('Оригинал')], [1, '1:1'], [4 / 3, '4:3'], [3 / 4, '3:4'], [16 / 9, '16:9']];

  function load(file) {
    return new Promise(function (ok, fail) {
      var img = new Image();
      img.onload = function () { ok(img); };
      img.onerror = fail;
      img.src = URL.createObjectURL(file);
    });
  }
  function canvas(w, h) { var c = document.createElement('canvas'); c.width = Math.max(1, Math.round(w)); c.height = Math.max(1, Math.round(h)); return c; }
  function toFile(cv, name) {
    return new Promise(function (ok) {
      cv.toBlob(function (b) { ok(new File([b], (name || 'photo').replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' })); }, 'image/jpeg', 0.9);
    });
  }

  function open(file, opts) {
    opts = opts || {};
    return load(file).then(function (img) {
      return new Promise(function (done) {
        var k0 = Math.min(1, MAX / Math.max(img.width, img.height));
        var W0 = Math.round(img.width * k0), H0 = Math.round(img.height * k0);
        var st = { rot: 0, flip: false, crop: null, aspect: opts.avatar ? 1 : 0, adj: { b: 0, c: 0, s: 0, w: 0, f: 0, v: 0 }, ops: [],
                   mode: opts.avatar ? 'crop' : 'draw', tool: 'pen', color: COLORS[2], size: 2, param: 'b' };
        function dims() { return st.rot % 2 ? { w: H0, h: W0 } : { w: W0, h: H0 }; }
        function full() { var d = dims(); return { x: 0, y: 0, w: d.w, h: d.h }; }
        function fit(aspect, around) {            // самая большая рамка с такими пропорциями внутри фото, по центру прежней
          var d = dims(), w = d.w, h = d.h;
          if (aspect > 0) { if (w / h > aspect) w = h * aspect; else h = w / aspect; }
          var cx = around ? around.x + around.w / 2 : d.w / 2, cy = around ? around.y + around.h / 2 : d.h / 2;
          return { x: Math.max(0, Math.min(d.w - w, cx - w / 2)), y: Math.max(0, Math.min(d.h - h, cy - h / 2)), w: w, h: h };
        }
        st.crop = fit(st.aspect);

        var box = document.createElement('div');
        box.className = 'pedit pedit--v2' + (opts.avatar ? ' pedit--avatar' : '');
        box.innerHTML =
          '<div class="pedit__top"><button type="button" data-a="cancel" aria-label="' + T('Отмена') + '">' + svg('close') + '</button>' +
          '<button type="button" data-a="undo" aria-label="' + T('Отменить шаг') + '">' + svg('undo') + '</button><span class="pedit__title"></span>' +
          '<button type="button" data-a="done" class="pedit__ok">' + (opts.done || T('Готово')) + '</button></div>' +
          '<div class="pedit__stage"><canvas></canvas></div>' +
          '<div class="pedit__panel"></div>' +
          (opts.avatar ? '' : '<div class="pedit__modes">' +
            [['crop', T('Кадр'), 'crop'], ['adjust', T('Цвет'), 'adjust'], ['draw', T('Рисунок'), 'pencil'], ['text', T('Текст'), 'type']].map(function (m) {
              return '<button type="button" data-mode="' + m[0] + '">' + svg(m[2]) + '<span>' + m[1] + '</span></button>'; }).join('') + '</div>');
        document.body.appendChild(box);
        var cv = box.querySelector('canvas'), ctx = cv.getContext('2d'), panel = box.querySelector('.pedit__panel'), title = box.querySelector('.pedit__title');

        /* ---------- картинка: поворот и отражение → цвет (по пикселям — работает в любом браузере) ---------- */
        function base(q) {
          var d = dims(), c = canvas(d.w * q, d.h * q), x = c.getContext('2d');
          if (st.flip) { x.translate(c.width, 0); x.scale(-1, 1); }
          x.translate(c.width / 2, c.height / 2); x.rotate(st.rot * Math.PI / 2);
          x.drawImage(img, -W0 * q / 2, -H0 * q / 2, W0 * q, H0 * q);
          return c;
        }
        function adjust(c) {
          var a = st.adj;
          if (!a.b && !a.c && !a.s && !a.w && !a.f) return c;
          var out = canvas(c.width, c.height), x = out.getContext('2d');
          x.drawImage(c, 0, 0);
          var id = x.getImageData(0, 0, out.width, out.height), p = id.data;
          var B = a.b * 70, C = a.c >= 0 ? 1 + a.c * 0.9 : 1 + a.c * 0.6, S = 1 + a.s, Wm = a.w * 28, F = Math.max(0, a.f);
          for (var i = 0; i < p.length; i += 4) {
            var r = p[i] + B, g = p[i + 1] + B, b = p[i + 2] + B;
            r = (r - 128) * C + 128; g = (g - 128) * C + 128; b = (b - 128) * C + 128;
            var gray = 0.299 * r + 0.587 * g + 0.114 * b;
            r = gray + (r - gray) * S + Wm; g = gray + (g - gray) * S; b = gray + (b - gray) * S - Wm;
            if (F) { r = r * (1 - F * 0.32) + F * 46; g = g * (1 - F * 0.32) + F * 46; b = b * (1 - F * 0.32) + F * 46; }
            p[i] = r; p[i + 1] = g; p[i + 2] = b;
          }
          x.putImageData(id, 0, 0);
          return out;
        }
        function vignette(x, rx, ry, rw, rh) {
          if (st.adj.v <= 0) return;
          var g = x.createRadialGradient(rx + rw / 2, ry + rh / 2, Math.min(rw, rh) * 0.28, rx + rw / 2, ry + rh / 2, Math.max(rw, rh) * 0.74);
          g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,' + (st.adj.v * 0.78) + ')');
          x.fillStyle = g; x.fillRect(rx, ry, rw, rh);
        }
        function drawOps(x, q, region) {
          x.save(); x.scale(q, q); x.translate(-region.x, -region.y);
          st.ops.forEach(function (o) {
            if (o.text) {
              x.font = '700 ' + o.size + 'px system-ui, sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle';
              x.lineWidth = o.size / 7; x.strokeStyle = o.color === '#111827' ? '#fff' : 'rgba(0,0,0,.55)'; x.lineJoin = 'round';
              x.strokeText(o.text, o.x, o.y); x.fillStyle = o.color; x.fillText(o.text, o.x, o.y);
              return;
            }
            x.globalAlpha = o.marker ? 0.42 : 1; x.strokeStyle = o.color; x.fillStyle = o.color; x.lineWidth = o.w; x.lineCap = x.lineJoin = 'round';
            x.beginPath();
            if (o.arrow) {
              var a = o.pts[0], b = o.pts[o.pts.length - 1], ang = Math.atan2(b[1] - a[1], b[0] - a[0]), hd = o.w * 4.2;
              x.moveTo(a[0], a[1]); x.lineTo(b[0], b[1]); x.stroke();
              x.beginPath(); x.moveTo(b[0], b[1]);
              x.lineTo(b[0] - hd * Math.cos(ang - 0.45), b[1] - hd * Math.sin(ang - 0.45));
              x.lineTo(b[0] - hd * Math.cos(ang + 0.45), b[1] - hd * Math.sin(ang + 0.45)); x.closePath(); x.fill();
            } else {
              o.pts.forEach(function (pt, i) { if (i) x.lineTo(pt[0], pt[1]); else x.moveTo(pt[0], pt[1]); });
              if (o.pts.length === 1) x.lineTo(o.pts[0][0] + 0.1, o.pts[0][1]);
              x.stroke();
            }
            x.globalAlpha = 1;
          });
          x.restore();
        }

        var prevQ = 1, prevBase = null, prevAdj = null;
        function rebuild() { var d = dims(); prevQ = Math.min(1, PREVIEW / Math.max(d.w, d.h)); prevBase = base(prevQ); prevAdj = adjust(prevBase); }
        function region() { return st.mode === 'crop' ? full() : st.crop; }
        function paint() {
          var r = region(), q = prevQ, c = st.crop;
          cv.width = Math.round(r.w * q); cv.height = Math.round(r.h * q);
          ctx.drawImage(prevAdj, r.x * q, r.y * q, r.w * q, r.h * q, 0, 0, cv.width, cv.height);
          vignette(ctx, (c.x - r.x) * q, (c.y - r.y) * q, c.w * q, c.h * q);
          drawOps(ctx, q, r);
          if (st.mode !== 'crop') return;
          var x0 = c.x * q, y0 = c.y * q, w = c.w * q, h = c.h * q, px = cv.width / cv.getBoundingClientRect().width || 1;
          ctx.save();
          ctx.fillStyle = 'rgba(11,13,22,.66)'; ctx.beginPath(); ctx.rect(0, 0, cv.width, cv.height);
          if (opts.avatar) { ctx.moveTo(x0 + w, y0 + h / 2); ctx.arc(x0 + w / 2, y0 + h / 2, w / 2, 0, Math.PI * 2, true); } else ctx.rect(x0, y0 + h, w, -h);
          ctx.fill('evenodd');
          ctx.strokeStyle = 'rgba(255,255,255,.95)'; ctx.lineWidth = 1.5 * px; ctx.strokeRect(x0, y0, w, h);
          ctx.strokeStyle = 'rgba(255,255,255,.35)'; ctx.lineWidth = px; ctx.beginPath();
          for (var i = 1; i < 3; i++) { ctx.moveTo(x0 + w * i / 3, y0); ctx.lineTo(x0 + w * i / 3, y0 + h); ctx.moveTo(x0, y0 + h * i / 3); ctx.lineTo(x0 + w, y0 + h * i / 3); }
          ctx.stroke();
          ctx.strokeStyle = '#fff'; ctx.lineWidth = 4 * px; ctx.lineCap = 'round'; var L = 20 * px; ctx.beginPath();
          [[x0, y0, 1, 1], [x0 + w, y0, -1, 1], [x0, y0 + h, 1, -1], [x0 + w, y0 + h, -1, -1]].forEach(function (k) {
            ctx.moveTo(k[0] + k[2] * L, k[1]); ctx.lineTo(k[0], k[1]); ctx.lineTo(k[0], k[1] + k[3] * L); });
          ctx.stroke(); ctx.restore();
        }
        var raf = 0;
        function repaintAdj() { if (raf) return; raf = requestAnimationFrame(function () { raf = 0; prevAdj = adjust(prevBase); paint(); }); }

        /* ---------- панели ---------- */
        function colorsHtml() { return '<span class="pedit__colors">' + COLORS.map(function (c) { return '<button type="button" data-c="' + c + '" style="background:' + c + '"' + (c === st.color ? ' class="on"' : '') + '></button>'; }).join('') + '</span>'; }
        function panelHtml() {
          if (st.mode === 'crop') {
            return '<div class="pedit__row">' + (opts.avatar ? '<span class="pedit__hint">' + T('Двигайте рамку и тяните за углы') + '</span>' :
              '<div class="pedit__chips">' + ASPECTS.map(function (a) { return '<button type="button" data-aspect="' + a[0] + '"' + (st.aspectKey === a[0] || (!st.aspectKey && a[0] === 0) ? ' class="on"' : '') + '>' + a[1] + '</button>'; }).join('') + '</div>') + '</div>' +
              '<div class="pedit__row pedit__row--c"><button type="button" class="pedit__ib" data-a="rotate" aria-label="' + T('Повернуть') + '">' + svg('rotate') + '</button>' +
              '<button type="button" class="pedit__ib" data-a="flip" aria-label="' + T('Отразить') + '">' + svg('flip') + '</button>' +
              '<button type="button" class="pedit__tb" data-a="reset">' + T('Сбросить') + '</button></div>';
          }
          if (st.mode === 'adjust') {
            var cur = ADJ.filter(function (a) { return a[0] === st.param; })[0], min = (st.param === 'f' || st.param === 'v') ? 0 : -100;
            return '<div class="pedit__chips">' + ADJ.map(function (a) { return '<button type="button" data-param="' + a[0] + '"' + (a[0] === st.param ? ' class="on"' : '') + (st.adj[a[0]] ? ' data-set="1"' : '') + '>' + svg(a[2]) + a[1] + '</button>'; }).join('') + '</div>' +
              '<div class="pedit__row"><input type="range" min="' + min + '" max="100" value="' + Math.round(st.adj[st.param] * 100) + '" data-range="adj" aria-label="' + cur[1] + '"><output>' + Math.round(st.adj[st.param] * 100) + '</output>' +
              '<button type="button" class="pedit__tb" data-a="enhance">' + svg('wand') + T('Улучшить') + '</button></div>';
          }
          if (st.mode === 'draw') {
            return '<div class="pedit__row"><span class="pedit__tools2">' + [['pen', 'pencil', T('Карандаш')], ['marker', 'marker', T('Маркер')], ['arrow', 'arrow', T('Стрелка')]].map(function (t) {
              return '<button type="button" class="pedit__ib' + (st.tool === t[0] ? ' on' : '') + '" data-tool="' + t[0] + '" aria-label="' + t[2] + '">' + svg(t[1]) + '</button>'; }).join('') + '</span>' + colorsHtml() + '</div>' +
              '<div class="pedit__row"><span class="pedit__hint">' + T('Толщина') + '</span><input type="range" min="1" max="6" step="0.5" value="' + st.size + '" data-range="size" aria-label="' + T('Толщина') + '"></div>';
          }
          return '<div class="pedit__row"><input type="text" class="pedit__input" maxlength="80" placeholder="' + T('Напишите текст') + '"><button type="button" class="pedit__tb pedit__tb--p" data-a="addtext">' + T('Добавить') + '</button></div>' +
            '<div class="pedit__row">' + colorsHtml() + '<span class="pedit__hint">' + T('Надпись можно двигать пальцем') + '</span></div>';
        }
        function ui() {
          panel.innerHTML = panelHtml();
          title.textContent = opts.avatar ? T('Фото профиля') : { crop: T('Кадр'), adjust: T('Цвет'), draw: T('Рисунок'), text: T('Текст') }[st.mode];
          box.querySelectorAll('[data-mode]').forEach(function (b) { b.classList.toggle('on', b.dataset.mode === st.mode); });
          cv.style.cursor = st.mode === 'draw' ? 'crosshair' : st.mode === 'adjust' ? 'default' : 'grab';
          paint();
        }

        /* ---------- жесты ---------- */
        function at(e) { var b = cv.getBoundingClientRect(), r = region(); return [r.x + (e.clientX - b.left) / b.width * r.w, r.y + (e.clientY - b.top) / b.height * r.h]; }
        var drag = null;
        function textAt(p) {
          for (var i = st.ops.length - 1; i >= 0; i--) {
            var o = st.ops[i]; if (!o.text) continue;
            ctx.font = '700 ' + o.size + 'px system-ui, sans-serif';
            var w = ctx.measureText(o.text).width / 2 + o.size * 0.3;
            if (Math.abs(p[0] - o.x) < w && Math.abs(p[1] - o.y) < o.size * 0.8) return o;
          }
          return null;
        }
        cv.addEventListener('pointerdown', function (e) {
          e.preventDefault();
          var p = at(e), c = st.crop, r = region(), tol = 30 * r.w / cv.getBoundingClientRect().width;
          if (st.mode === 'crop') {
            var corners = [[c.x, c.y], [c.x + c.w, c.y], [c.x, c.y + c.h], [c.x + c.w, c.y + c.h]], hit = -1;
            corners.forEach(function (k, i) { if (Math.abs(p[0] - k[0]) < tol && Math.abs(p[1] - k[1]) < tol) hit = i; });
            if (hit >= 0) drag = { corner: hit, fx: corners[3 - hit][0], fy: corners[3 - hit][1] };
            else if (p[0] > c.x && p[0] < c.x + c.w && p[1] > c.y && p[1] < c.y + c.h) drag = { move: true, dx: p[0] - c.x, dy: p[1] - c.y };
          } else if (st.mode === 'draw') {
            var w = Math.max(2.5, dims().w / 300) * st.size * (st.tool === 'marker' ? 3 : 1);
            drag = { op: { pts: [p], color: st.color, w: w, marker: st.tool === 'marker', arrow: st.tool === 'arrow' } };
            st.ops.push(drag.op);
          } else if (st.mode === 'text') {
            var o = textAt(p); if (o) drag = { text: o, dx: p[0] - o.x, dy: p[1] - o.y };
          }
          if (drag) { cv.setPointerCapture(e.pointerId); paint(); }
        });
        cv.addEventListener('pointermove', function (e) {
          if (!drag) return;
          var p = at(e), d = dims(), c = st.crop, min = Math.min(d.w, d.h) * 0.12;
          if (drag.move) { c.x = Math.max(0, Math.min(d.w - c.w, p[0] - drag.dx)); c.y = Math.max(0, Math.min(d.h - c.h, p[1] - drag.dy)); }
          else if (drag.corner !== undefined) {
            var px = Math.max(0, Math.min(d.w, p[0])), py = Math.max(0, Math.min(d.h, p[1]));
            var w = Math.max(min, Math.abs(px - drag.fx)), h = Math.max(min, Math.abs(py - drag.fy)), sx = drag.corner % 2 ? 1 : -1, sy = drag.corner > 1 ? 1 : -1;
            if (st.aspect > 0) {
              h = w / st.aspect;
              var maxW = sx > 0 ? d.w - drag.fx : drag.fx, maxH = sy > 0 ? d.h - drag.fy : drag.fy;
              if (w > maxW) { w = maxW; h = w / st.aspect; }
              if (h > maxH) { h = maxH; w = h * st.aspect; }
            }
            c.x = sx > 0 ? drag.fx : drag.fx - w; c.y = sy > 0 ? drag.fy : drag.fy - h; c.w = w; c.h = h;
          } else if (drag.op) { if (drag.op.arrow) drag.op.pts[1] = p; else drag.op.pts.push(p); }
          else if (drag.text) { drag.text.x = p[0] - drag.dx; drag.text.y = p[1] - drag.dy; }
          paint();
        });
        function up() { drag = null; }
        cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);

        /* ---------- поворот и отражение переносят рамку и рисунки вместе с фото ---------- */
        function rotate() {
          var d = dims(), c = st.crop;
          st.ops.forEach(function (o) { if (o.text) { var x = o.x; o.x = d.h - o.y; o.y = x; } else o.pts = o.pts.map(function (p) { return [d.h - p[1], p[0]]; }); });
          st.crop = { x: d.h - (c.y + c.h), y: c.x, w: c.h, h: c.w };
          st.rot = (st.rot + 1) % 4;
          if (st.aspect > 0) st.aspect = 1 / st.aspect;
        }
        function flip() {
          var d = dims();
          st.ops.forEach(function (o) { if (o.text) o.x = d.w - o.x; else o.pts = o.pts.map(function (p) { return [d.w - p[0], p[1]]; }); });
          st.crop.x = d.w - st.crop.x - st.crop.w; st.flip = !st.flip;
        }
        function changed() {
          var d = dims(), c = st.crop, a = st.adj;
          return st.rot || st.flip || st.ops.length || a.b || a.c || a.s || a.w || a.f || a.v || Math.abs(c.w - d.w) > 1 || Math.abs(c.h - d.h) > 1;
        }
        function result() {
          var c = st.crop, src = adjust(base(1)), out = canvas(c.w, c.h), x = out.getContext('2d');
          x.drawImage(src, c.x, c.y, c.w, c.h, 0, 0, out.width, out.height);
          vignette(x, 0, 0, out.width, out.height);
          drawOps(x, 1, c);
          if (!opts.avatar) return out;
          var sq = canvas(640, 640); sq.getContext('2d').drawImage(out, 0, 0, 640, 640); return sq;
        }
        function close(value) { URL.revokeObjectURL(img.src); box.remove(); done(value); }

        box.addEventListener('click', function (e) {
          var b = e.target.closest('button'); if (!b) return;
          if (b.dataset.mode) { st.mode = b.dataset.mode; ui(); return; }
          if (b.dataset.c) { st.color = b.dataset.c; ui(); return; }
          if (b.dataset.tool) { st.tool = b.dataset.tool; ui(); return; }
          if (b.dataset.param) { st.param = b.dataset.param; ui(); return; }
          if (b.dataset.aspect !== undefined) {
            var a = parseFloat(b.dataset.aspect), d = dims();
            st.aspectKey = a; st.aspect = a < 0 ? d.w / d.h : a;
            if (st.aspect > 0) st.crop = fit(st.aspect, st.crop);
            ui(); return;
          }
          var act = b.dataset.a;
          if (act === 'cancel') close(null);
          else if (act === 'undo') { st.ops.pop(); paint(); }
          else if (act === 'rotate') { rotate(); rebuild(); ui(); }
          else if (act === 'flip') { flip(); rebuild(); ui(); }
          else if (act === 'reset') { st.rot = 0; st.flip = false; st.aspect = opts.avatar ? 1 : 0; st.aspectKey = 0; st.crop = fit(st.aspect); rebuild(); ui(); }
          else if (act === 'enhance') { var on = st.adj.c === 0.18 && st.adj.s === 0.22; st.adj.c = on ? 0 : 0.18; st.adj.s = on ? 0 : 0.22; st.adj.b = on ? 0 : 0.06; prevAdj = adjust(prevBase); ui(); }
          else if (act === 'addtext') {
            var inp = panel.querySelector('.pedit__input'), text = (inp.value || '').trim(); if (!text) { inp.focus(); return; }
            var c = st.crop; st.ops.push({ text: text.slice(0, 80), x: c.x + c.w / 2, y: c.y + c.h / 2, color: st.color, size: Math.max(22, c.w / 14) });
            inp.value = ''; inp.blur(); paint();
          } else if (act === 'done') {
            if (!opts.avatar && !changed()) { close(file); return; }
            b.disabled = true; toFile(result(), file.name).then(close);
          }
        });
        box.addEventListener('input', function (e) {
          var r = e.target.dataset && e.target.dataset.range; if (!r) return;
          if (r === 'size') { st.size = parseFloat(e.target.value); return; }
          st.adj[st.param] = parseInt(e.target.value, 10) / 100;
          var out = panel.querySelector('output'); if (out) out.textContent = e.target.value;
          repaintAdj();
        });
        box.addEventListener('keydown', function (e) { if (e.key === 'Enter' && e.target.classList.contains('pedit__input')) { e.preventDefault(); panel.querySelector('[data-a=addtext]').click(); } });
        window.addEventListener('resize', paint);
        rebuild(); ui();
      });
    }).catch(function () { return file; });
  }

  window.ilm4PhotoEdit = function (file) { return open(file, { done: T('Отправить') }); };
  window.ilm4Crop = function (file) { return open(file, { avatar: true }); };

  // аватар профиля, группы, канала: выбрал файл → рамка-квадрат с кругом → в то же поле кладём готовый квадрат
  document.addEventListener('change', function (e) {
    var input = e.target;
    if (!input.matches || !input.matches('input[type=file][data-crop], #id_avatar') || input.dataset.cropped || !input.files[0] || !window.DataTransfer) return;
    e.stopImmediatePropagation();
    window.ilm4Crop(input.files[0]).then(function (f) {
      if (!f) { input.value = ''; return; }
      var dt = new DataTransfer(); dt.items.add(f); input.files = dt.files;
      input.dataset.cropped = '1';
      input.dispatchEvent(new Event('change', { bubbles: true }));
      delete input.dataset.cropped;
    });
  }, true);
})();
