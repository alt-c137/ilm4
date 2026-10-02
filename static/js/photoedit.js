/* Редактор фото перед отправкой (как в Telegram): рисовать, писать текст, отменять шаги.
   И обрезка аватара: двигаешь и приближаешь фото в круге.
     ilm4PhotoEdit(file) → Promise<File|null>   (null — отмена)
     ilm4Crop(file)      → Promise<File|null> */
(function () {
  var L = { ru: ['Отправить', 'Отмена', 'Текст', 'Напишите текст', 'Готово', 'Двигайте фото и приближайте', 'Без правок'],
            uz: ['Yuborish', 'Bekor qilish', 'Matn', 'Matn yozing', 'Tayyor', 'Rasmni suring va yaqinlashtiring', 'O‘zgarishsiz'],
            en: ['Send', 'Cancel', 'Text', 'Type your text', 'Done', 'Drag and zoom the photo', 'Unchanged'] }[document.documentElement.lang] ||
          ['Отправить', 'Отмена', 'Текст', 'Напишите текст', 'Готово', 'Двигайте фото и приближайте', 'Без правок'];
  var COLORS = ['#ffffff', '#111827', '#ef4444', '#f59e0b', '#22c55e', '#3b82f6', '#a855f7'];

  function load(file) {
    return new Promise(function (ok, fail) {
      var img = new Image();
      img.onload = function () { ok(img); };
      img.onerror = fail;
      img.src = URL.createObjectURL(file);
    });
  }
  function shell(html) {
    var box = document.createElement('div');
    box.className = 'pedit';
    box.innerHTML = html;
    document.body.appendChild(box);
    return box;
  }
  function toFile(canvas, name) {
    return new Promise(function (ok) {
      canvas.toBlob(function (b) { ok(new File([b], (name || 'photo').replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' })); }, 'image/jpeg', 0.9);
    });
  }

  window.ilm4PhotoEdit = function (file) {
    return load(file).then(function (img) {
      return new Promise(function (done) {
        var k = Math.min(1, 1600 / Math.max(img.width, img.height));
        var box = shell('<div class="pedit__top"><button type="button" data-a="cancel" aria-label="' + L[1] + '">✕</button>' +
          '<button type="button" data-a="undo" aria-label="undo">↶</button><span></span>' +
          '<button type="button" data-a="raw" class="pedit__txt">' + L[6] + '</button></div>' +
          '<div class="pedit__stage"><canvas></canvas></div>' +
          '<div class="pedit__tools"><span class="pedit__colors"></span><button type="button" data-a="text" class="pedit__txt">Аа ' + L[2] + '</button></div>' +
          '<button type="button" data-a="send" class="pedit__send">' + L[0] + '</button>');
        var cv = box.querySelector('canvas'), ctx = cv.getContext('2d'), ops = [], color = COLORS[2], cur = null, placing = false;
        cv.width = Math.round(img.width * k); cv.height = Math.round(img.height * k);
        var pen = Math.max(4, cv.width / 130);
        box.querySelector('.pedit__colors').innerHTML = COLORS.map(function (c) { return '<button type="button" data-c="' + c + '" style="background:' + c + '"></button>'; }).join('');
        function mark() { box.querySelectorAll('[data-c]').forEach(function (b) { b.classList.toggle('on', b.dataset.c === color); }); box.querySelector('[data-a=text]').classList.toggle('on', placing); }
        function draw() {
          ctx.drawImage(img, 0, 0, cv.width, cv.height);
          ops.forEach(function (o) {
            if (o.text) {
              ctx.font = '700 ' + o.size + 'px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
              ctx.lineWidth = o.size / 7; ctx.strokeStyle = o.color === '#111827' ? '#fff' : 'rgba(0,0,0,.55)'; ctx.lineJoin = 'round';
              ctx.strokeText(o.text, o.x, o.y); ctx.fillStyle = o.color; ctx.fillText(o.text, o.x, o.y);
            } else {
              ctx.strokeStyle = o.color; ctx.lineWidth = o.w; ctx.lineCap = ctx.lineJoin = 'round'; ctx.beginPath();
              o.pts.forEach(function (p, i) { if (i) ctx.lineTo(p[0], p[1]); else ctx.moveTo(p[0], p[1]); });
              if (o.pts.length === 1) ctx.lineTo(o.pts[0][0] + 0.1, o.pts[0][1]);
              ctx.stroke();
            }
          });
        }
        function at(e) { var r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * cv.width / r.width, (e.clientY - r.top) * cv.height / r.height]; }
        cv.addEventListener('pointerdown', function (e) {
          e.preventDefault();
          var p = at(e);
          if (placing) {
            var t = prompt(L[3]);
            if (t) ops.push({ text: t.slice(0, 80), x: p[0], y: p[1], color: color, size: Math.max(22, cv.width / 16) });
            placing = false; mark(); draw(); return;
          }
          cv.setPointerCapture(e.pointerId);
          cur = { pts: [p], color: color, w: pen }; ops.push(cur); draw();
        });
        cv.addEventListener('pointermove', function (e) { if (cur) { cur.pts.push(at(e)); draw(); } });
        function up() { cur = null; }
        cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
        function close(result) { URL.revokeObjectURL(img.src); box.remove(); done(result); }
        box.addEventListener('click', function (e) {
          var b = e.target.closest('button'); if (!b) return;
          if (b.dataset.c) { color = b.dataset.c; mark(); return; }
          var a = b.dataset.a;
          if (a === 'cancel') close(null);
          else if (a === 'undo') { ops.pop(); draw(); }
          else if (a === 'text') { placing = !placing; mark(); }
          else if (a === 'raw') close(file);
          else if (a === 'send') { if (!ops.length) close(file); else toFile(cv, file.name).then(close); }
        });
        mark(); draw();
      });
    }).catch(function () { return file; });
  };

  window.ilm4Crop = function (file) {
    return load(file).then(function (img) {
      return new Promise(function (done) {
        var box = shell('<div class="pedit__top"><button type="button" data-a="cancel" aria-label="' + L[1] + '">✕</button><span>' + L[5] + '</span></div>' +
          '<div class="pedit__stage"><div class="pcrop"><canvas width="640" height="640"></canvas></div></div>' +
          '<div class="pedit__tools"><input type="range" min="100" max="400" value="100" aria-label="zoom"></div>' +
          '<button type="button" data-a="send" class="pedit__send">' + L[4] + '</button>');
        var cv = box.querySelector('canvas'), ctx = cv.getContext('2d'), zoom = 1, ox = 0, oy = 0, drag = null;
        var base = 640 / Math.min(img.width, img.height);
        function draw() {
          var s = base * zoom, w = img.width * s, h = img.height * s;
          ox = Math.min(0, Math.max(640 - w, ox)); oy = Math.min(0, Math.max(640 - h, oy));
          ctx.fillStyle = '#000'; ctx.fillRect(0, 0, 640, 640); ctx.drawImage(img, ox, oy, w, h);
        }
        ox = (640 - img.width * base) / 2; oy = (640 - img.height * base) / 2;
        cv.addEventListener('pointerdown', function (e) { cv.setPointerCapture(e.pointerId); drag = [e.clientX, e.clientY, ox, oy]; });
        cv.addEventListener('pointermove', function (e) {
          if (!drag) return;
          var k = 640 / cv.getBoundingClientRect().width;
          ox = drag[2] + (e.clientX - drag[0]) * k; oy = drag[3] + (e.clientY - drag[1]) * k; draw();
        });
        cv.addEventListener('pointerup', function () { drag = null; });
        box.querySelector('input').addEventListener('input', function (e) {
          var z = e.target.value / 100, cx = (320 - ox) / (base * zoom), cy = (320 - oy) / (base * zoom);
          zoom = z; ox = 320 - cx * base * zoom; oy = 320 - cy * base * zoom; draw();
        });
        function close(result) { URL.revokeObjectURL(img.src); box.remove(); done(result); }
        box.addEventListener('click', function (e) {
          var b = e.target.closest('button'); if (!b) return;
          if (b.dataset.a === 'cancel') close(null); else toFile(cv, file.name).then(close);
        });
        draw();
      });
    }).catch(function () { return file; });
  };

  // аватар профиля, группы, канала: выбрал файл → обрезка в круге → в то же поле кладём готовый квадрат
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
