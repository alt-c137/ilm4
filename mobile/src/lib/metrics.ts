/**
 * Сколько времени человек проводит на экранах приложения — по разделам, без подробностей (секунды и название раздела).
 * Нужно владельцу, чтобы видеть, какие разделы живые, а какие лишние (сайт → /moderation/stats/).
 * Копим в памяти и раз в минуту (и при сворачивании) отправляем на сервер.
 */
import { AppState } from 'react-native';

import { api } from './api';

const SECTION: Record<string, string> = {
  '': 'home', chats: 'chat', chat: 'chat', prayer: 'prayer', 'prayer-month': 'prayer', 'prayer-settings': 'prayer', qibla: 'prayer',
  tracker: 'tracker', habits: 'tracker', services: 'catalog', me: 'profile', user: 'profile', 'profile-edit': 'profile', privacy: 'settings',
  settings: 'settings', 'tabs-setup': 'settings', 'chat-look': 'settings', places: 'map', 'tab-map': 'map', nikah: 'nikah', 'tab-nikah': 'nikah',
  news: 'news', 'tab-news': 'news', feed: 'feed', 'tab-feed': 'feed', space: 'communities', 'tab-communities': 'communities',
  assistant: 'assistant', wallet: 'wallet', notifications: 'notifications', my: 'my', publish: 'my',
  'tab-buy': 'buy', 'tab-jobs': 'jobs', 'tab-trips': 'transport', 'tab-forum': 'forum', 'tab-library': 'library',
};

let current = '', since = Date.now(), active = true;
const acc: Record<string, { t: number; o: number }> = {};

function close() {
  if (!current || !active) return;
  const row = (acc[current] ??= { t: 0, o: 0 });
  row.t += Math.max(0, Date.now() - since) / 1000;
  since = Date.now();
}

/** Экран сменился: путь из expo-router, например «/chat/15» или «/pubs/jobs». */
export function trackScreen(path: string) {
  close();
  const parts = path.split('/').filter(Boolean);
  const next = parts[0] === 'pubs' || parts[0] === 'pub' ? (parts[1] ?? 'other') : (SECTION[parts[0] ?? ''] ?? 'other');
  if (next !== current) (acc[next] ??= { t: 0, o: 0 }).o = 1;
  current = next;
  since = Date.now();
}

export function flushMetrics() {
  close();
  const items = Object.entries(acc).filter(([, v]) => v.t >= 1 || v.o).map(([s, v]) => ({ s, t: Math.min(90, Math.round(v.t)), o: v.o }));
  for (const key of Object.keys(acc)) delete acc[key];
  if (items.length) api('/metrics/', { body: { items } }).catch(() => {});
}

let started = false;
export function startMetrics() {
  if (started) return;
  started = true;
  setInterval(flushMetrics, 60000);
  AppState.addEventListener('change', (state) => {
    if (state === 'active') { active = true; since = Date.now(); } else { close(); active = false; flushMetrics(); }
  });
}
