/* ilm4 · лента как во ВКонтакте: лайки, комментарии под записью, «поделиться», бесконечная прокрутка,
   новая запись с фото, сторис (кружки сверху, просмотр на весь экран), правка и удаление своих записей. */
(function () {
  'use strict';
  var root = document.getElementById('feed');
  if (!root) return;
  var csrf = (document.querySelector('#feed-csrf [name=csrfmiddlewaretoken]') || document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';
  function T(s) { return window._t ? window._t(s) : s; }
  function toast(text) {
    var t = document.createElement('div'); t.className = 'tg__toast'; t.textContent = text;
    document.body.appendChild(t); setTimeout(function () { t.remove(); }, 3200);
  }
  function post(url, data) {
    var fd = data instanceof FormData ? data : new FormData();
    if (!(data instanceof FormData)) Object.keys(data || {}).forEach(function (k) { fd.append(k, data[k]); });
    fd.append('csrfmiddlewaretoken', csrf);
    return fetch(url, { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'fetch' } })
      .then(function (r) {
        if (r.redirected && /\/accounts\/login/.test(r.url)) { location.href = r.url; throw new Error(''); }
        return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || T('Не удалось')); return j; });
      });
  }
  function fail(e) { if (e && e.message) toast(e.message); }
  var authed = !!document.querySelector('.fnew') || !!document.querySelector('.fcom__form');

  // запомнить выбор «Главная / Лента»
  document.addEventListener('click', function (e) {
    var h = e.target.closest('[data-hometab]');
    if (h) try { localStorage.setItem('ilm4.home', h.dataset.hometab); } catch (err) { /* приватный режим */ }
  });

  /* ---------- карточки ---------- */
  root.addEventListener('click', function (e) {
    var card = e.target.closest('.fcard');
    var like = e.target.closest('[data-like]');
    if (like && card) {
      e.preventDefault();
      if (!authed) { location.href = '/accounts/login/?next=' + encodeURIComponent(location.pathname); return; }
      like.classList.toggle('on'); like.classList.add('pop');
      setTimeout(function () { like.classList.remove('pop'); }, 300);
      post('/feed/like/', { target: card.dataset.key }).then(function (j) {
        like.classList.toggle('on', j.liked); like.querySelector('span').textContent = j.likes || '';
      }).catch(function (err) { like.classList.toggle('on'); fail(err); });
      return;
    }
    var keep = e.target.closest('[data-save]');
    if (keep && card) {
      e.preventDefault();
      if (!authed) { location.href = '/accounts/login/?next=' + encodeURIComponent(location.pathname); return; }
      keep.classList.toggle('on');
      post('/feed/save/', { target: card.dataset.key }).then(function (j) { keep.classList.toggle('on', j.saved); toast(j.saved ? T('Сохранено') : T('Убрано из сохранённого')); })
        .catch(function (err) { keep.classList.toggle('on'); fail(err); });
      return;
    }
    var rp = e.target.closest('[data-repost-now]');
    if (rp && card) {
      e.preventDefault();
      if (!authed) { location.href = '/accounts/login/?next=' + encodeURIComponent(location.pathname); return; }
      if (!confirm(T('Сделать репост на свою стену?'))) return;
      post('/feed/new/', { repost_of: rp.dataset.repostNow, text: '' }).then(function () {
        var n = rp.querySelector('span'); n.textContent = (parseInt(n.textContent || '0', 10) + 1); toast(T('Запись появилась на вашей стене'));
      }).catch(fail);
      return;
    }
    var com = e.target.closest('[data-comments]');
    if (com && card) { e.preventDefault(); toggleComments(card); return; }
    var share = e.target.closest('[data-share]');
    if (share && card) { e.preventDefault(); shareMenu(share, card); return; }
    var more = e.target.closest('.fcard__more');
    if (more) { more.previousElementSibling.classList.remove('is-long'); more.remove(); return; }
    var img = e.target.closest('.fgrid__i');
    if (img && window.ilm4Photos) {
      e.preventDefault();
      var all = Array.prototype.slice.call(img.parentNode.querySelectorAll('.fgrid__i'));
      window.ilm4Photos(all.map(function (a) { return { url: a.dataset.full }; }), all.indexOf(img), {});
      return;
    }
    var fa = e.target.closest('[data-fa]');
    if (fa && card) {
      e.preventDefault();
      var d = fa.closest('details'); if (d) d.open = false;
      if (fa.dataset.fa === 'delete') {
        if (!confirm(T('Удалить запись?'))) return;
        post('/feed/post/' + card.dataset.post + '/delete/').then(function () { card.remove(); }).catch(fail);
      } else {
        var box = card.querySelector('.fcard__txt'), old = box ? box.innerText : '';
        var text = prompt(T('Изменить запись'), old);
        if (text === null) return;
        post('/feed/post/' + card.dataset.post + '/edit/', { text: text }).then(function () { location.reload(); }).catch(fail);
      }
    }
  });
  document.addEventListener('click', function (e) {
    document.querySelectorAll('details.tp__menu[open]').forEach(function (d) { if (!d.contains(e.target)) d.open = false; });
  });

  /* ---------- комментарии под записью ---------- */
  function toggleComments(card) {
    var box = card.querySelector('.fcom');
    if (!box.hidden) { box.hidden = true; return; }
    box.hidden = false; box.innerHTML = '<p class="fcom__none">' + T('Загрузка…') + '</p>';
    fetch('/feed/c/' + encodeURIComponent(card.dataset.key) + '/?json=1', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); }).then(function (j) { box.innerHTML = j.html; var ta = box.querySelector('textarea'); if (ta) ta.focus(); })
      .catch(function () { box.innerHTML = '<p class="fcom__none">' + T('Нет соединения — попробуйте ещё раз') + '</p>'; });
  }
  root.addEventListener('submit', function (e) {
    var f = e.target.closest('.fcom__form'); if (!f) return;
    e.preventDefault();
    var fd = new FormData(f); fd.append('target', f.dataset.target);
    var box = f.closest('.fcom'), card = f.closest('.fcard');
    post('/feed/comment/', fd).then(function (j) {
      box.innerHTML = j.html;
      var n = card && card.querySelector('[data-comments] span'); if (n) n.textContent = j.count || '';
    }).catch(fail);
  });
  root.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey && e.target.matches('.fcom__form textarea') && !('ontouchstart' in window)) {
      e.preventDefault(); e.target.form.requestSubmit();
    }
  });
  root.addEventListener('click', function (e) {
    var r = e.target.closest('[data-creply]');
    if (r) {
      var f = r.closest('.fcom').querySelector('.fcom__form'); if (!f) return;
      f.reply_to.value = r.dataset.creply;
      var to = f.querySelector('.fcom__to'); to.textContent = '↩ ' + r.dataset.name; to.hidden = false;
      f.text.focus(); return;
    }
    var d = e.target.closest('[data-cdel]');
    if (d && confirm(T('Удалить комментарий?'))) {
      post('/feed/comment/' + d.dataset.cdel + '/delete/').then(function () { d.closest('.fcom__row').remove(); }).catch(fail);
    }
  });

  /* ---------- поделиться ---------- */
  var menu = null;
  function shareMenu(btn, card) {
    if (menu) menu.remove();
    menu = document.createElement('div'); menu.className = 'ctxmenu pop';
    var url = location.origin + btn.dataset.url;
    var html = '';
    if (btn.dataset.repost && authed) html += '<button type="button" data-s="wall">' + T('На своей стене') + '</button>';
    if (navigator.share) html += '<button type="button" data-s="native">' + T('Отправить…') + '</button>';
    html += '<button type="button" data-s="copy">' + T('Скопировать ссылку') + '</button>';
    menu.innerHTML = html;
    document.body.appendChild(menu);
    var r = btn.getBoundingClientRect();
    menu.style.left = Math.max(8, Math.min(r.left, innerWidth - menu.offsetWidth - 8)) + 'px';
    menu.style.top = Math.max(8, Math.min(r.bottom + 6, innerHeight - menu.offsetHeight - 8)) + 'px';
    menu.addEventListener('click', function (e) {
      var b = e.target.closest('[data-s]'); if (!b) return;
      var s = b.dataset.s; menu.remove(); menu = null;
      if (s === 'wall') post('/feed/new/', { repost_of: btn.dataset.repost, text: '' }).then(function () { toast(T('Запись появилась на вашей стене')); }).catch(fail);
      else if (s === 'native') navigator.share({ url: url }).catch(function () {});
      else if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { toast(T('Ссылка скопирована')); });
    });
  }
  document.addEventListener('click', function (e) { if (menu && !e.target.closest('.ctxmenu') && !e.target.closest('[data-share]')) { menu.remove(); menu = null; } });

  /* ---------- бесконечная прокрутка ---------- */
  var list = document.getElementById('feed-list'), more = document.getElementById('feed-more'), loading = false;
  function loadMore() {
    var next = root.dataset.next;
    if (loading || !next || !list) return;
    loading = true;
    fetch('?more=1&tab=' + encodeURIComponent(root.dataset.tab || '') + '&before=' + encodeURIComponent(next), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (j) { list.insertAdjacentHTML('beforeend', j.html); root.dataset.next = j.next || ''; if (!j.next) more.hidden = true; })
      .catch(function () {}).then(function () { loading = false; });
  }
  if (more && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (es) { if (es[0].isIntersecting) loadMore(); }, { rootMargin: '600px' }).observe(more);
  }

  /* ---------- новая запись ---------- */
  var fnew = document.getElementById('fnew');
  if (fnew) {
    var ta = fnew.querySelector('textarea'), pics = document.getElementById('fnew-pics'), input = document.getElementById('fnew-photos');
    ta.addEventListener('input', function () { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 260) + 'px'; fnew.classList.toggle('is-open', !!ta.value || input.files.length > 0); });
    ta.addEventListener('focus', function () { fnew.classList.add('is-open'); });
    input.addEventListener('change', function () {
      pics.innerHTML = '';
      Array.prototype.slice.call(input.files, 0, 10).forEach(function (f) {
        var u = URL.createObjectURL(f); pics.insertAdjacentHTML('beforeend', '<img src="' + u + '" alt="">');
      });
      if (input.files.length > 10) toast(T('Не больше 10 фото в одной записи'));
      fnew.classList.add('is-open');
    });
    fnew.addEventListener('submit', function (e) {
      e.preventDefault();
      var btn = fnew.querySelector('[type=submit]'); btn.disabled = true;
      post(fnew.action, new FormData(fnew)).then(function () { location.href = '/feed/?tab=' + (root.dataset.tab || 'for_you'); })
        .catch(function (err) { btn.disabled = false; fail(err); });
    });
  }

  /* ---------- сторис ---------- */
  var sfile = document.getElementById('story-file');
  if (sfile) sfile.addEventListener('change', function () {
    var f = sfile.files[0]; if (!f) return;
    var caption = prompt(T('Подпись к сторис (можно пусто)'), '') || '';
    var fd = new FormData(); fd.append('photo', f); fd.append('caption', caption);
    post('/feed/stories/new/', fd).then(function () { location.reload(); }).catch(fail);
  });
  var groups = [];
  try { groups = JSON.parse(document.getElementById('stories-data').textContent) || []; } catch (e) { groups = []; }
  var sv = null, sg = 0, si = 0, stimer = null;
  function storyBox() {
    sv = document.createElement('div'); sv.className = 'sview'; sv.hidden = true;
    sv.innerHTML = '<div class="sview__bars"></div><div class="sview__top"><span class="sview__who"></span><button type="button" class="sview__x" aria-label="' + T('Закрыть') + '">×</button></div>' +
      '<img class="sview__img" alt=""><p class="sview__cap"></p><button type="button" class="sview__nav sview__nav--l" aria-label="' + T('Назад') + '"></button>' +
      '<button type="button" class="sview__nav sview__nav--r" aria-label="' + T('Вперёд') + '"></button><div class="sview__foot"></div>';
    document.body.appendChild(sv);
    sv.querySelector('.sview__x').addEventListener('click', closeStory);
    sv.querySelector('.sview__nav--l').addEventListener('click', function () { step(-1); });
    sv.querySelector('.sview__nav--r').addEventListener('click', function () { step(1); });
    document.addEventListener('keydown', function (e) { if (sv.hidden) return; if (e.key === 'Escape') closeStory(); if (e.key === 'ArrowRight') step(1); if (e.key === 'ArrowLeft') step(-1); });
  }
  function drawStory() {
    var g = groups[sg], s = g.items[si];
    sv.querySelector('.sview__img').src = s.url;
    sv.querySelector('.sview__cap').textContent = s.caption || '';
    sv.querySelector('.sview__who').textContent = g.author.name;
    sv.querySelector('.sview__bars').innerHTML = g.items.map(function (_x, i) { return '<i class="' + (i < si ? 'done' : i === si ? 'now' : '') + '"></i>'; }).join('');
    var foot = sv.querySelector('.sview__foot');
    foot.innerHTML = g.mine ? '<button type="button" data-sv="viewers">' + T('Кто смотрел') + '</button><button type="button" data-sv="delete" class="bad">' + T('Удалить') + '</button>' : '';
    foot.onclick = function (e) {
      var b = e.target.closest('[data-sv]'); if (!b) return;
      clearTimeout(stimer);
      if (b.dataset.sv === 'delete') { if (confirm(T('Удалить сторис?'))) post('/feed/stories/' + s.id + '/delete/').then(function () { location.reload(); }).catch(fail); return; }
      post('/feed/stories/' + s.id + '/viewers/').then(function (j) {
        alert(j.items.length ? j.items.map(function (v) { return v.name + (v.reaction ? ' ' + v.reaction : ''); }).join('\n') : T('Пока никто не смотрел'));
      }).catch(fail);
    };
    if (!g.mine && !s.seen) { s.seen = true; post('/feed/stories/' + s.id + '/view/').catch(function () {}); }
    clearTimeout(stimer); stimer = setTimeout(function () { step(1); }, 6000);
  }
  function step(by) {
    var g = groups[sg];
    si += by;
    if (si >= g.items.length) { sg++; si = 0; }
    if (si < 0) { sg--; si = sg >= 0 ? groups[sg].items.length - 1 : 0; }
    if (sg < 0 || sg >= groups.length) { closeStory(); return; }
    drawStory();
  }
  function closeStory() { clearTimeout(stimer); if (sv) sv.hidden = true; document.documentElement.classList.remove('pview-open'); }
  root.addEventListener('click', function (e) {
    var b = e.target.closest('[data-story]'); if (!b) return;
    if (!sv) storyBox();
    sg = +b.dataset.story; si = 0;
    var firstNew = groups[sg].items.findIndex(function (x) { return !x.seen; });
    if (firstNew > 0) si = firstNew;
    sv.hidden = false; document.documentElement.classList.add('pview-open'); b.classList.remove('is-new');
    drawStory();
  });
})();
