import Constants from 'expo-constants';
import { router, Stack, usePathname } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { onPhoneRequired } from '@/lib/api';
import { openSiteUrl } from '@/lib/links';
import { startMetrics, trackScreen } from '@/lib/metrics';
import { Notifications } from '@/lib/notify';
import { AppProvider, useApp } from '@/state/app';
import { IncomingCalls } from '@/ui/incoming';
import { Button, Icon, Txt } from '@/ui/kit';

SplashScreen.preventAutoHideAsync().catch(() => {});

function newer(a: string, b: string) {
  const pa = a.split('.').map(Number), pb = b.split('.').map(Number);
  for (let i = 0; i < 3; i++) if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) > (pb[i] || 0);
  return false;
}

/** Время по разделам приложения — для сводки владельца (lib/metrics.ts). Ничего не рисует. */
function Metrics() {
  const pathname = usePathname();
  useEffect(() => { startMetrics(); }, []);
  useEffect(() => { trackScreen(pathname); }, [pathname]);
  return null;
}

/** Нажали на уведомление — открываем нужный экран (только телефон). */
function NotificationRouter() {
  const last = Notifications!.useLastNotificationResponse();
  useEffect(() => {
    const url = last?.notification.request.content.data?.url;
    if (typeof url === 'string' && url) openSiteUrl(url);
  }, [last]);
  return null;
}

function Root() {
  const { ready, c, dark, config, t } = useApp();

  useEffect(() => {
    if (ready) SplashScreen.hideAsync().catch(() => {});
  }, [ready]);

  // сервер просит подтвердить номер (подача объявлений, никях) — один экран на всё приложение
  useEffect(() => {
    let last = 0;
    onPhoneRequired((why) => {
      if (Date.now() - last < 4000) return;
      last = Date.now();
      router.push({ pathname: '/verify-phone', params: { why } });
    });
  }, []);

  if (!ready) return <View style={{ flex: 1, backgroundColor: c.bg }} />;

  const version = Constants.expoConfig?.version ?? '1.0.0';
  if (config?.min_version && newer(config.min_version, version)) {
    return (
      <View style={{ flex: 1, backgroundColor: c.bg, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 14 }}>
        <Icon name="cloud-download-outline" size={48} color={c.accent} />
        <Txt kind="h2" style={{ textAlign: 'center' }}>{t('Обновите приложение')}</Txt>
        <Txt kind="muted" style={{ textAlign: 'center' }}>{t('Эта версия больше не поддерживается. Установите новую из магазина приложений.')}</Txt>
        <Button title={t('Понятно')} onPress={() => {}} kind="soft" />
      </View>
    );
  }

  return (
    <>
      <StatusBar style={dark ? 'light' : 'dark'} />
      {Notifications ? <NotificationRouter /> : null}
      <IncomingCalls />
      <Metrics />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: c.bg }, animation: 'slide_from_right' }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="login" options={{ presentation: 'modal', animation: 'slide_from_bottom' }} />
        <Stack.Screen name="report" options={{ presentation: 'modal', animation: 'slide_from_bottom' }} />
        <Stack.Screen name="verify-phone" options={{ presentation: 'modal', animation: 'slide_from_bottom' }} />
      </Stack>
    </>
  );
}

export default function Layout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <AppProvider>
          <Root />
        </AppProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
