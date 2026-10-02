/** Переходы: адреса сайта → экраны приложения; открытие сайта уже со входом. */
import { router } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';

import { api, API_URL } from './api';

const PUB_PREFIX: Record<string, string> = {
  buy: 'buy', jobs: 'jobs', map: 'places', health: 'doctors', migration: 'stories', forum: 'topics',
};

/** Ссылка из уведомления (адрес сайта) → экран приложения. Неизвестное — сайт внутри браузера. */
export function openSiteUrl(url: string) {
  const path = url.replace(API_URL, '');
  let m = path.match(/^\/chat\/(\d+)\/?/);
  if (m) return router.push(`/chat/${m[1]}`);
  m = path.match(/^\/c\/([A-Za-z0-9_]+)\/?$/);                 // публичный адрес канала
  if (m) return router.push({ pathname: '/chat/channels', params: { handle: m[1] } });
  m = path.match(/^\/chat\/join\/([\w-]+)\/?$/);               // ссылка-приглашение
  if (m) return router.push({ pathname: '/chat/channels', params: { code: m[1] } });
  if (path.startsWith('/chat/channels')) return router.push('/chat/channels');
  m = path.match(/^\/tracker\/join\/([\w-]+)\/?$/);            // приглашение в общий трекер
  if (m) return router.push({ pathname: '/habits/join', params: { code: m[1] } });
  if (path.startsWith('/tracker')) return router.push('/tracker');
  m = path.match(/^\/accounts\/u\/(\d+)\/?$/);               // страница человека
  if (m) return router.push(`/user/${m[1]}`);
  m = path.match(/^\/nikah\/match\/(\d+)\/?/);
  if (m) return router.push(`/nikah/match/${m[1]}`);
  m = path.match(/^\/nikah\/(\d+)\/?$/);
  if (m) return router.push(`/nikah/${m[1]}`);
  if (path.startsWith('/nikah/interests') || path.startsWith('/nikah/chats')) return router.push('/nikah/lists');
  if (path.startsWith('/nikah')) return router.push('/nikah');
  if (path.startsWith('/prayer')) return router.push('/prayer');
  m = path.match(/^\/news\/(\d+)\/?$/);
  if (m) return router.push(`/news/${m[1]}`);
  m = path.match(/^\/(buy|jobs|map|health|migration|forum)\/(\d+)\/?$/);
  if (m) return router.push(`/pub/${PUB_PREFIX[m[1]]}/${m[2]}`);
  if (path.startsWith('/wallet')) return router.push('/wallet');
  if (path.startsWith('/notifications')) return router.push('/notifications');
  return openWeb(path || '/');
}

/** Открыть страницу сайта во встроенном браузере — уже со входом в аккаунт
 *  (одноразовая ссылка на 2 минуты). Нужна для оплаты и подачи публикаций. */
export async function openWeb(path: string, loggedIn = true) {
  let url = API_URL + path;
  if (loggedIn) {
    try {
      const r = await api<{ url: string }>('/auth/web-link/', { body: { next: path } });
      url = r.url;
    } catch {
      /* без входа — просто страница */
    }
  }
  await WebBrowser.openBrowserAsync(url, { presentationStyle: WebBrowser.WebBrowserPresentationStyle.PAGE_SHEET });
}
