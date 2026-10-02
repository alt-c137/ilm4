import { useFocusEffect } from 'expo-router';
import * as ScreenCapture from 'expo-screen-capture';
import { useCallback } from 'react';
import { Platform } from 'react-native';

import { TabMode } from '@/ui/kit';

import NikahHome from '../nikah/index';

/** Никях можно поставить нижней кнопкой (Профиль → «Нижние кнопки»). Скриншоты запрещены, пока вкладка открыта. */
export default function Tab() {
  useFocusEffect(useCallback(() => {
    if (Platform.OS === 'web') return;
    ScreenCapture.preventScreenCaptureAsync('nikah-tab').catch(() => {});
    return () => { ScreenCapture.allowScreenCaptureAsync('nikah-tab').catch(() => {}); };
  }, []));
  return <TabMode.Provider value><NikahHome /></TabMode.Provider>;
}
