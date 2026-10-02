/**
 * Отправка вложений чата — как в Telegram:
 * - видео сжимается на телефоне ДО отправки (Android — react-native-compressor; iPhone сжимает сам при выборе);
 * - большой файл идёт частями по 4 МБ: виден прогресс, обрыв связи не начинает всё заново.
 *
 * Сжатие на телефоне работает только в собранном приложении (EAS). В Expo Go модуля нет —
 * тогда видео уходит как есть, и его пережимает сервер (apps/chat/transcode.py).
 */
import Constants, { ExecutionEnvironment } from 'expo-constants';
import { File } from 'expo-file-system';
import { Platform } from 'react-native';

import { api, API_URL, ApiError, authHeaders } from './api';
import { t } from './i18n';

export const BIG = 16 * 1048576;     // крупнее — частями
const RETRIES = 8;

export type Stage = 'compress' | 'upload';
export type OnProgress = (stage: Stage, done: number, total: number) => void;
export type UploadOpts = { duration?: number; silent?: boolean; schedule?: string };

const inExpoGo = Constants.executionEnvironment === ExecutionEnvironment.StoreClient;

/** Сжать видео до нужной высоты (720p по умолчанию). Не получилось или нет модуля — вернуть исходник. */
export async function compressVideo(uri: string, height: number, onProgress?: OnProgress): Promise<string> {
  if (Platform.OS !== 'android' || inExpoGo) return uri;
  try {
    // подключаем только здесь: в Expo Go этого модуля нет, и обычный import уронил бы приложение при запуске
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { Video } = require('react-native-compressor') as typeof import('react-native-compressor');
    const side = Math.round((height * 16) / 9);                       // длинная сторона кадра
    const bitrate = height >= 1080 ? 4_500_000 : height >= 720 ? 2_200_000 : 1_100_000;
    const out = await Video.compress(uri, { compressionMethod: 'manual', maxSize: side, bitrate, minimumFileSizeForCompress: 2 },
      (p) => onProgress?.('compress', Math.round(p * 100), 100));
    return out || uri;
  } catch {
    return uri;
  }
}

export function fileSizeOf(uri: string): number {
  try {
    return new File(uri).size || 0;
  } catch {
    return 0;
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Загрузка частями. Возвращает готовое сообщение (как обычная отправка). */
export async function uploadInParts(threadId: string | number, kind: 'file' | 'video', uri: string, name: string,
  opts: UploadOpts = {}, onProgress?: OnProgress, cancelled?: () => boolean): Promise<any> {
  const file = new File(uri);
  const size = file.size || 0;
  if (!size) throw new ApiError(t('Файл пустой'));
  const start = await api<{ upload: string; part: number }>(`/chat/${threadId}/upload/begin/`, {
    body: { kind, name, size, duration: Math.round(opts.duration ?? 0), silent: !!opts.silent, schedule: opts.schedule ?? '' },
  });
  const id = start.upload;
  const handle = file.open();
  try {
    let offset = 0;
    let tries = 0;
    onProgress?.('upload', 0, size);
    while (offset < size) {
      if (cancelled?.()) {
        api(`/chat/upload/${id}/cancel/`, { body: {} }).catch(() => {});
        throw new ApiError(t('Отправка отменена'), 0, 'cancelled');
      }
      handle.offset = offset;
      const bytes = handle.readBytes(Math.min(start.part, size - offset));
      let res: Response;
      try {
        res = await fetch(`${API_URL}/api/v1/chat/upload/${id}/part/?offset=${offset}`, {
          method: 'POST', headers: { ...authHeaders(), 'Content-Type': 'application/octet-stream' }, body: bytes,
        });
      } catch {
        // связь пропала: ждём, спрашиваем сервер, сколько он получил, и продолжаем с того же места
        if (++tries > RETRIES) throw new ApiError(t('Нет соединения с интернетом'), 0, 'offline', {}, true);
        await sleep(Math.min(15000, 1500 * tries));
        try {
          offset = (await api<{ received: number }>(`/chat/upload/${id}/`)).received;
        } catch (e) {
          if (e instanceof ApiError && !e.offline) throw e;
        }
        continue;
      }
      const j = await res.json().catch(() => null);
      if ((res.ok || res.status === 409) && typeof j?.received === 'number') {
        offset = j.received;
        tries = 0;
        onProgress?.('upload', offset, size);
        continue;
      }
      throw new ApiError(j?.error || t('Ошибка сервера ({n})', { n: res.status }), res.status);
    }
  } finally {
    handle.close();
  }
  return api(`/chat/upload/${id}/finish/`, { body: {}, timeout: 60000 });
}
