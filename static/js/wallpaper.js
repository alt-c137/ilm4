/* Фон переписки: узор, цвет или своё фото. Хранится на этом устройстве (как обои в Telegram). */
(function () {
  var KEY = 'ilm4.wall';
  function get() { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } }
  function set(w) { try { localStorage.setItem(KEY, JSON.stringify(w)); return true; } catch (e) { return false; } }
  function apply(el, w) {
    w = w || get();
    el.dataset.wall = w.photo ? 'none' : (w.pattern || 'shapes');
    el.classList.toggle('has-color', !!w.color && !w.photo);
    el.classList.toggle('has-photo', !!w.photo);
    if (w.color && !w.photo) el.style.setProperty('--wall-bg', w.color); else el.style.removeProperty('--wall-bg');
    var layer = el.querySelector(':scope > .tg__wallphoto');
    if (w.photo) {
      if (!layer) { layer = document.createElement('div'); layer.className = 'tg__wallphoto'; el.insertBefore(layer, el.firstChild); }
      layer.style.backgroundImage = 'url(' + w.photo + ')';
      el.style.setProperty('--wall-blur', (w.blur || 0) + 'px');
      el.style.setProperty('--wall-dim', String((w.dim == null ? 15 : w.dim) / 100));
    } else if (layer) layer.remove();
  }
  window.ilm4Wall = { get: get, set: set, apply: apply };
  document.querySelectorAll('.tg__main').forEach(function (el) { apply(el); });
})();
