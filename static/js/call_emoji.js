/* ilm4 · 4 эмодзи для сверки ключей звонка (как в Telegram). docs/MESSENGER.md §2.3.
   Голос и видео WebRTC шифруются ключами, созданными на устройствах (DTLS-SRTP). Отпечатки этих
   ключей есть в SDP («a=fingerprint»). Если сервер подменит ключи, отпечатки у собеседников
   разойдутся — и эмодзи будут разными. Список ДОЛЖЕН совпадать с mobile/src/lib/callEmoji.ts
   (проверяет тест apps/chat/tests/test_call_emoji.py). */
(function () {
  'use strict';
  var EMOJI = ["🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮", "🐸", "🐵", "🐔", "🐧", "🐦", "🐤", "🦆", "🦅", "🦉", "🐺", "🐴", "🦄", "🐝", "🐛", "🦋", "🐌", "🐞", "🐢", "🐍", "🦎", "🐙", "🦑", "🦀", "🐡", "🐠", "🐟", "🐬", "🐳", "🦈", "🐊", "🐅", "🐆", "🦓", "🦍", "🐘", "🦛", "🦏", "🐪", "🦒", "🦘", "🐃", "🐏", "🐑", "🦙", "🐐", "🦌", "🐓", "🦃", "🦚", "🦜", "🦢", "🦩", "🌵", "🌲", "🌳", "🌴", "🌱", "🌿", "🍀", "🍁", "🍄", "🌷", "🌹", "🌻", "🌼", "🌸", "🌍", "🌙", "⭐", "⚡", "🔥", "🌈", "☀️", "⛄", "🌊", "💧", "🍎", "🍐", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🍒", "🍑", "🥭", "🍍", "🥥", "🥝", "🍅", "🥑", "🥕", "🌽", "🥦", "🧀", "🥚", "🍞", "🥨", "🍯", "⚽", "🏀", "🏈", "🎾", "🏐", "🎳", "🏓", "🏸", "🔑", "🔒", "🔔", "📌", "✏️", "📚", "🎈", "🚲"];
  function fingerprint(sdp) {
    var m = /a=fingerprint:sha-256 ([0-9A-Fa-f:]+)/.exec(sdp || '');
    return m ? m[1].replace(/:/g, '').toUpperCase() : '';
  }
  /* Промис: 4 эмодзи или [] (если отпечатков нет). */
  function callEmoji(localSdp, remoteSdp) {
    var a = fingerprint(localSdp), b = fingerprint(remoteSdp);
    if (!a || !b || !(window.crypto && crypto.subtle)) return Promise.resolve([]);
    var text = a < b ? a + '|' + b : b + '|' + a;
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)).then(function (buf) {
      var h = new Uint8Array(buf);
      return [EMOJI[h[0] % 128], EMOJI[h[1] % 128], EMOJI[h[2] % 128], EMOJI[h[3] % 128]];
    });
  }
  window.ilmCallEmoji = callEmoji;
})();
