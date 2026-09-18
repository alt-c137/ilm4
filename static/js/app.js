// Общий мелкий интерактив. Сейчас: баннер кук (согласие на 180 дней).
var ckbar = document.getElementById('ckbar');
if (ckbar) {
  document.getElementById('ckok').addEventListener('click', function () {
    document.cookie = 'ilm4_cookie=1;path=/;max-age=15552000;samesite=lax';
    ckbar.remove();
  });
}
