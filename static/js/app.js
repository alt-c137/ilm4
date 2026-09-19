// Общий интерактив: баннер кук + красивый выбор файла для ВСЕХ форм.
var ckbar = document.getElementById('ckbar');
if (ckbar) {
  document.getElementById('ckok').addEventListener('click', function () {
    document.cookie = 'ilm4_cookie=1;path=/;max-age=15552000;samesite=lax';
    ckbar.remove();
  });
}

// input[type=file] -> кнопка «📎 Выбрать файл» + имя выбранного файла
document.querySelectorAll('input[type=file]').forEach(function (input) {
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
