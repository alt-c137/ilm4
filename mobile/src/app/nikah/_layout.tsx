import { Stack } from 'expo-router';
import { usePreventScreenCapture } from 'expo-screen-capture';
import { Platform } from 'react-native';

import { useApp } from '@/state/app';

/** Все экраны никяха: скриншоты и запись экрана запрещены (Android — полностью, iOS 13+). */
function NoCapture() {
  usePreventScreenCapture('nikah');
  return null;
}

export default function NikahLayout() {
  const { c } = useApp();
  return (
    <>
      {Platform.OS !== 'web' ? <NoCapture /> : null}
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: c.bg }, animation: 'slide_from_right' }} />
    </>
  );
}
