/** Уведомления:
 *  - азан-напоминания — локальные, телефон сам «звонит» во время намаза (без интернета);
 *  - пуши от сервера (сообщения, симпатии никяха) — Expo Push, нужна сборка приложения
 *    (в Expo Go на Android пуши недоступны — это ограничение Expo Go, не приложения).
 */
import { isRunningInExpoGo } from 'expo';
import Constants from 'expo-constants';
import * as Device from 'expo-device';
import { Platform } from 'react-native';

import { api } from './api';
import { t } from './i18n';
import { dayTimes, FARD, type Asr, type Method, type Place, type PrayerKey } from './prayer';

/** Expo Go на Android: модуль уведомлений там «сломан» уже при подключении (ограничение Expo Go с SDK 53).
 *  Поэтому подключаем его только там, где он работает: в собранном приложении (Android/iOS) и в Expo Go на iPhone. */
export const isExpoGoAndroid = Platform.OS === 'android' && isRunningInExpoGo();

type NotificationsModule = typeof import('expo-notifications');
let N: NotificationsModule | null = null;
if (Platform.OS !== 'web' && !isExpoGoAndroid) {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    N = require('expo-notifications');
  } catch {
    N = null;
  }
}
/** Модуль уведомлений или null (веб, Expo Go на Android). */
export const Notifications = N;

N?.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: true, shouldSetBadge: false, shouldShowBanner: true, shouldShowList: true,
  }),
});

export const PRAYER_NAMES: Record<PrayerKey, string> = {
  fajr: 'Фаджр', sunrise: 'Восход', dhuhr: 'Зухр', asr: 'Аср', maghrib: 'Магриб', isha: 'Иша',
};

async function ensureChannels() {
  if (!N || Platform.OS !== 'android') return;
  await N!.setNotificationChannelAsync('prayer', {
    name: t('Время намаза'), importance: N!.AndroidImportance.HIGH, vibrationPattern: [0, 300, 200, 300],
  });
  await N!.setNotificationChannelAsync('default', {
    name: t('Сообщения и события'), importance: N!.AndroidImportance.DEFAULT,
  });
}

export async function askPermission(): Promise<boolean> {
  if (!N) return false;
  await ensureChannels();
  const cur = await N!.getPermissionsAsync();
  if (cur.granted) return true;
  const req = await N!.requestPermissionsAsync();
  return req.granted;
}

export type PrayerAlerts = { enabled: Partial<Record<PrayerKey, boolean>>; before: number };

/** Перепланировать напоминания на 7 дней вперёд (35 штук — в пределах лимита iOS 64). */
export async function schedulePrayers(place: Place | null, method: Method, asr: Asr, alerts: PrayerAlerts) {
  if (!N) return 0;
  const all = await N!.getAllScheduledNotificationsAsync();
  await Promise.all(all.filter((n) => n.content.data?.kind === 'prayer')
    .map((n) => N!.cancelScheduledNotificationAsync(n.identifier)));
  if (!place || !FARD.some((k) => alerts.enabled[k])) return 0;
  if (!(await askPermission())) return 0;
  const now = Date.now();
  let n = 0;
  for (let i = 0; i < 7; i++) {
    const day = dayTimes(place, new Date(now + i * 86400000), method, asr);
    for (const k of FARD) {
      if (!alerts.enabled[k]) continue;
      const at = new Date(day.at[k].getTime() - alerts.before * 60000);
      if (at.getTime() <= now + 5000) continue;
      await N!.scheduleNotificationAsync({
        content: {
          title: alerts.before ? t('{name} через {m} мин', { name: t(PRAYER_NAMES[k]), m: alerts.before }) : t('Время намаза: {name}', { name: t(PRAYER_NAMES[k]) }),
          body: `${day.times[k]} · ${place.name}`,
          data: { kind: 'prayer', url: '/prayer' },
          sound: 'default',
          ...(Platform.OS === 'android' ? { channelId: 'prayer' } : {}),
        } as any,
        trigger: { type: N!.SchedulableTriggerInputTypes.DATE, date: at, channelId: 'prayer' } as any,
      });
      n++;
    }
  }
  return n;
}

/** Регистрация телефона для пушей с сервера. Тихо пропускается, где пуши невозможны. */
export async function registerPush(): Promise<void> {
  try {
    if (!N || !Device.isDevice) return;
    const projectId = (Constants.expoConfig?.extra as any)?.eas?.projectId || (Constants as any).easConfig?.projectId;
    if (!projectId) return; // проект ещё не подключён к EAS — см. mobile/README.md
    if (!(await askPermission())) return;
    const { data } = await N!.getExpoPushTokenAsync({ projectId });
    await api('/push/', { body: { token: data, platform: Platform.OS } });
  } catch {
    /* Expo Go на Android и т. п. — пуши недоступны, остальное работает */
  }
}
