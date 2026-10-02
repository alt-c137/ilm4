/**
 * Связь с сервером ilm4 (/api/v1/…).
 * - вход по токену (заголовок Authorization), язык — X-Lang;
 * - каждый удачный GET кешируется: без интернета приложение показывает последнее загруженное.
 */
import Constants from 'expo-constants';

import { t } from './i18n';
import { getToken, load, save } from './storage';

const extra = (Constants.expoConfig?.extra ?? {}) as { apiUrl?: string };
export const API_URL: string = (process.env.EXPO_PUBLIC_API_URL || extra.apiUrl || 'https://ilm4.com').replace(/\/$/, '');

let lang = 'ru';
let authToken: string | null = null;
let onUnauthorized: (() => void) | null = null;
let onReach: ((ok: boolean) => void) | null = null;
let onPhone: ((why: string) => void) | null = null;

export function setApiLang(l: string) {
  lang = l;
}
export function setApiToken(t: string | null) {
  authToken = t;
}
export function onAuthLost(fn: () => void) {
  onUnauthorized = fn;
}
/** Сервер доступен / недоступен — для плашки «нет интернета» (надёжнее, чем статус сети телефона). */
export function onReachability(fn: (ok: boolean) => void) {
  onReach = fn;
}
/** Сервер ответил «нужен подтверждённый номер» (защита от ботов) — показать экран подтверждения. */
export function onPhoneRequired(fn: (why: string) => void) {
  onPhone = fn;
}
export function authHeaders(): Record<string, string> {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

export class ApiError extends Error {
  status: number;
  code: string;
  fields: Record<string, string>;
  offline: boolean;
  constructor(message: string, status = 0, code = '', fields: Record<string, string> = {}, offline = false) {
    super(message);
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.offline = offline;
  }
}

type Opts = { method?: string; body?: unknown; form?: FormData; timeout?: number };

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  if (authToken === null) authToken = await getToken();
  const headers: Record<string, string> = { Accept: 'application/json', 'X-Lang': lang, ...authHeaders() };
  let body: any;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opts.timeout ?? 20000);
  let res: Response;
  try {
    res = await fetch(API_URL + '/api/v1' + path, { method: opts.method ?? (body ? 'POST' : 'GET'), headers, body, signal: ctrl.signal });
  } catch {
    onReach?.(false);
    throw new ApiError(t('Нет соединения с интернетом'), 0, 'offline', {}, true);
  } finally {
    clearTimeout(timer);
  }
  onReach?.(true);
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    if (res.status === 401 && authToken) onUnauthorized?.();
    if (res.status === 403 && data?.code === 'phone') onPhone?.(data?.why || 'publish');
    throw new ApiError(data?.error || t('Ошибка сервера ({n})', { n: res.status }), res.status, data?.code || '', data?.fields || {});
  }
  return data as T;
}

/** GET с кешем: сначала свежие данные; нет сети — сохранённые (fromCache = true). */
export async function cachedGet<T = any>(path: string): Promise<{ data: T; fromCache: boolean }> {
  const key = `cache:${lang}:${path}`;
  try {
    const data = await api<T>(path);
    save(key, data);
    return { data, fromCache: false };
  } catch (e) {
    if (e instanceof ApiError && e.offline) {
      const old = await load<T | null>(key, null);
      if (old !== null) return { data: old, fromCache: true };
    }
    throw e;
  }
}

export async function peekCache<T = any>(path: string): Promise<T | null> {
  return load<T | null>(`cache:${lang}:${path}`, null);
}

/** Адрес файла вложения чата (отдаётся только участникам — по токену). */
export function chatFileUrl(id: number) {
  return `${API_URL}/api/v1/chat/file/${id}/`;
}

export function wsUrl(path: string) {
  return API_URL.replace(/^http/, 'ws') + path;
}
