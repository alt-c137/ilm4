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
  btn.textContent = '📎 Выбрать файл';
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
