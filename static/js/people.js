/* Профиль «как в Telegram»: вкладки, копирование по нажатию, раскрытие «Изменить», строки соцсетей. */
(function () {
  function toast(text) {
    var t = document.createElement('div');
    t.className = 'tp__toast'; t.textContent = text;
    document.body.appendChild(t);
    setTimeout(function () { t.classList.add('out'); }, 1400);
    setTimeout(function () { t.remove(); }, 1800);
  }
  var copied = document.documentElement.lang === 'en' ? 'Copied' : document.documentElement.lang === 'uz' ? 'Nusxalandi' : 'Скопировано';

  // меню «⋮»: нажал мимо — закрылось
  document.addEventListener('click', function (e) {
    document.querySelectorAll('details.tp__menu[open]').forEach(function (d) { if (!d.contains(e.target)) d.open = false; });
  });

  // вкладки: Публикации · Медиа · Файлы · Отзывы
  var tabs = document.querySelectorAll('.tp__tab');
  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      tabs.forEach(function (x) { x.classList.toggle('on', x === tab); });
      document.querySelectorAll('.tp__pane').forEach(function (p) { p.hidden = p.dataset.pane !== tab.dataset.tab; });
    });
  });

  // нажал на @имя или ник в Discord — скопировалось
  document.querySelectorAll('[data-copy]').forEach(function (el) {
    el.addEventListener('click', function () {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(el.dataset.copy).then(function () { toast(copied); });
    });
  });

  // «Изменить»: раскрыть нужный блок и поставить курсор
  document.querySelectorAll('[data-open]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      var box = document.getElementById(a.dataset.open);
      if (!box) return;
      e.preventDefault();
      box.open = true;
      box.scrollIntoView({ behavior: 'smooth', block: 'start' });
      var f = a.dataset.focus && document.getElementById(a.dataset.focus);
      if (f) setTimeout(function () { f.focus(); }, 300);
    });
  });
  if (location.hash && document.querySelector('details' + location.hash)) document.querySelector('details' + location.hash).open = true;

  // фото профиля: выбрал файл — сразу сохранить
  var ava = document.getElementById('id_avatar');
  if (ava) ava.addEventListener('change', function () { if (ava.files.length) ava.form.submit(); });

  // соцсети: добавить / убрать строку
  var rows = document.getElementById('link-rows'), add = document.getElementById('link-add');
  if (rows && add) {
    var blank = document.getElementById('link-blank').cloneNode(true);
    blank.removeAttribute('id');
    add.addEventListener('click', function () {
      var row = blank.cloneNode(true);
      rows.appendChild(row);
      row.querySelector('input').focus();
    });
    rows.addEventListener('click', function (e) {
      var del = e.target.closest('.lrow__del');
      if (!del) return;
      var row = del.closest('.lrow');
      if (rows.querySelectorAll('.lrow').length > 1) row.remove();
      else row.querySelector('input').value = '';
    });
  }
})();
