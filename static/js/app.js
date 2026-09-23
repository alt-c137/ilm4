// Общий интерактив: баннер кук + красивый выбор файла для ВСЕХ форм.
var ckbar = document.getElementById('ckbar');
if (ckbar) {
  document.getElementById('ckok').addEventListener('click', function () {
    document.cookie = 'ilm4_cookie=1;path=/;max-age=15552000;samesite=lax';
    ckbar.remove();
  });
}

// input[type=file] -> кнопка «📎 Выбрать файл» (кроме авы профиля — там клик по фото)
document.querySelectorAll('input[type=file]').forEach(function (input) {
  if (input.dataset.skip) return;
  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'filebtn';
  btn.innerHTML = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11.5 12.3 19.2a4.8 4.8 0 0 1-6.8-6.8l7.7-7.7a3.2 3.2 0 0 1 4.5 4.5l-7.6 7.7a1.6 1.6 0 0 1-2.3-2.3l7-7"/></svg>Выбрать файл';
  var name = document.createElement('span');
  name.className = 'filename';
  name.textContent = 'файл не выбран';
  input.parentNode.insertBefore(btn, input.nextSibling);
  btn.parentNode.insertBefore(name, btn.nextSibling);
  btn.addEventListener('click', function () { input.click(); });
  input.addEventListener('change', function () {
    name.textContent = input.files.length ? input.files[0].name : 'файл не выбран';
  });
});


// живой отсчёт до намаза: элементы .live-cd с data-ts (unix)
function fmtCd(s) {
  var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  var t = '';
  if (h) t += h + ' ч ';
  if (h || m) t += m + ' мин ';
  t += (x < 10 ? '0' : '') + x + ' сек';
  return 'через ' + t;
}
function tickCd() {
  var now = Math.floor(Date.now() / 1000);
  document.querySelectorAll('.live-cd').forEach(function (el) {
    var d = parseInt(el.dataset.ts, 10) - now;
    if (d <= 0) { location.reload(); return; }
    el.textContent = fmtCd(d);
  });
}
setInterval(tickCd, 1000);
tickCd();

// стрелки строк-каруселей: появляются при наведении, листают с прокруткой
document.querySelectorAll('.railnav').forEach(function (nav) {
  var row = nav.querySelector('.rail, .apps, .nav__row');
  if (!row) return;
  nav.querySelectorAll('.rail-arrow').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var first = row.querySelector('.app, .card, .qa, .rcard--news, .hcard--mini');
      var step = first ? first.offsetWidth + 14 : Math.max(320, row.clientWidth * 0.8);
      row.scrollBy({ left: btn.classList.contains('l') ? -step : step, behavior: 'smooth' });
    });
  });
});

// тёмная тема: переключатель у лого, состояние в куке ilm4_dark
var dt = document.getElementById('darktoggle');
if (dt) {
  dt.addEventListener('click', function () {
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    var next = dark ? '0' : '1';
    document.documentElement.setAttribute('data-theme', next === '1' ? 'dark' : 'light');
    document.cookie = 'ilm4_dark=' + next + ';path=/;max-age=31536000;samesite=lax';
    var mt = document.getElementById('meta-theme');
    if (mt) mt.setAttribute('content', next === '1' ? '#0e1016' : '#f2f3fb');
  });
}

// телефон: поиск раскрывается по кнопке-лупе
(function () {
  var t = document.getElementById('search-toggle');
  var top = document.getElementById('top');
  var form = document.getElementById('search');
  if (!t || !top || !form) return;
  t.addEventListener('click', function () {
    var open = top.classList.toggle('top--search');
    t.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) form.querySelector('input').focus();
  });
})();

// меню профиля: открытие по тапу (на тач-экранах нет hover), закрытие вне меню
(function () {
  var menu = document.getElementById('usermenu');
  var chip = document.getElementById('uchip');
  if (!menu || !chip) return;
  chip.addEventListener('click', function (e) {
    e.stopPropagation();
    var open = menu.classList.toggle('open');
    chip.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  document.addEventListener('click', function (e) {
    if (!menu.contains(e.target)) { menu.classList.remove('open'); chip.setAttribute('aria-expanded', 'false'); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { menu.classList.remove('open'); chip.setAttribute('aria-expanded', 'false'); }
  });
})();

// стрелки строк: скрываются на краях (дошёл до конца — «вперёд» исчезла)
function refreshArrows(nav, row) {
  var l = nav.querySelector('.rail-arrow.l');
  var r = nav.querySelector('.rail-arrow.r');
  if (!l || !r) return;
  var max = row.scrollWidth - row.clientWidth - 4;
  var atStart = row.scrollLeft <= 4;
  var atEnd = row.scrollLeft >= max;
  l.classList.toggle('hid', atStart);
  r.classList.toggle('hid', atEnd);
  row.classList.toggle('at-start', atStart);
  row.classList.toggle('at-end', atEnd);
}
document.querySelectorAll('.railnav').forEach(function (nav) {
  var row = nav.querySelector('.rail, .apps, .nav__row');
  if (!row) return;
  var upd = function () { refreshArrows(nav, row); };
  row.addEventListener('scroll', upd, { passive: true });
  window.addEventListener('resize', upd);
  upd();
});

// лента пилюль: при загрузке подрулить к активному разделу, а не сбрасываться в начало
(function () {
  var pill = document.querySelector('.nav__row a.on');
  var row = document.querySelector('.nav__row');
  if (!pill || !row) return;
  row.scrollLeft = Math.max(0, pill.offsetLeft - (row.clientWidth - pill.offsetWidth) / 2);
})();

// кнопка «Копировать» (контакты): data-copy="текст"
document.querySelectorAll('[data-copy]').forEach(function (b) {
  b.addEventListener('click', function () {
    var txt = b.dataset.copy, label = b.textContent;
    var done = function () { b.textContent = 'Скопировано'; b.classList.add('ok');
      setTimeout(function () { b.textContent = label; b.classList.remove('ok'); }, 1600); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(txt).then(done);
    else { var t = document.createElement('textarea'); t.value = txt; document.body.appendChild(t);
      t.select(); try { document.execCommand('copy'); done(); } catch (e) {} t.remove(); }
  });
});

// «Поделиться»: системное меню телефона (iOS/Android), иначе — копируем ссылку
document.querySelectorAll('[data-share]').forEach(function (b) {
  b.addEventListener('click', function () {
    var data = { title: b.dataset.share, url: location.href };
    if (navigator.share) { navigator.share(data).catch(function () {}); return; }
    var label = b.innerHTML;
    var done = function () { b.textContent = 'Ссылка скопирована'; setTimeout(function () { b.innerHTML = label; }, 1600); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(location.href).then(done);
  });
});
