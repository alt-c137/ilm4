// Переключение палитры «Апп»: подменяем три CSS-переменные и запоминаем выбор
// в куке ilm4_theme (сервер подхватит её при следующем запросе).
document.querySelectorAll('.sw').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var root = document.documentElement.style;
    root.setProperty('--accent', btn.dataset.accent);
    root.setProperty('--accent-d', btn.dataset.accentD);
    root.setProperty('--accent-soft', btn.dataset.accentSoft);
    document.cookie = 'ilm4_theme=' + btn.dataset.id +
      ';path=/;max-age=31536000;samesite=lax';
    document.querySelectorAll('.sw').forEach(function (b) { b.classList.remove('on'); });
    btn.classList.add('on');
  });
});
