/** Слушает личный канал /ws/me/: входящий звонок → окно «Ответить / Отклонить» на любом экране. */
import { router } from 'expo-router';
import { useEffect } from 'react';
import { Alert, AppState, Platform } from 'react-native';

import { authHeaders, wsUrl } from '@/lib/api';
import { t } from '@/lib/i18n';
import { callsSupported } from '@/lib/webrtc';
import { useApp } from '@/state/app';
import { getOpenThread } from '@/state/calls';

export function IncomingCalls() {
  const { user } = useApp();
  useEffect(() => {
    if (!user || Platform.OS === 'web' || !callsSupported) return;
    let sock: WebSocket | null = null;
    let stop = false;
    let retry: ReturnType<typeof setTimeout>;
    let shown = 0;
    const connect = () => {
      // @ts-expect-error — в React Native третий аргумент: заголовки
      sock = new WebSocket(wsUrl('/ws/me/'), null, { headers: authHeaders() });
      sock.onmessage = (e) => {
        const d = JSON.parse(e.data);
        if (d.action !== 'ring' || d.thread === getOpenThread() || shown === d.thread) return;
        shown = d.thread;
        Alert.alert(d.video ? t('Входящий видеозвонок') : t('Входящий аудиозвонок'), d.from_name, [
          { text: t('Отклонить'), style: 'cancel', onPress: () => { shown = 0; } },
          { text: t('Ответить'), onPress: () => { shown = 0; router.push({ pathname: '/chat/[id]', params: { id: String(d.thread), answer: '1' } }); } },
        ]);
      };
      sock.onclose = () => {
        if (!stop) retry = setTimeout(connect, 5000);
      };
    };
    connect();
    const sub = AppState.addEventListener('change', (s) => {
      if (s === 'active' && sock?.readyState !== WebSocket.OPEN) { sock?.close(); }
    });
    return () => {
      stop = true;
      clearTimeout(retry);
      sub.remove();
      sock?.close();
    };
  }, [user]);
  return null;
}
