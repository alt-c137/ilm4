import { SafeAreaView } from 'react-native-safe-area-context';

import { useApp } from '@/state/app';
import { Feed } from '@/ui/feed';
import { OfflineBar, Txt } from '@/ui/kit';

/** «Лента» нижней кнопкой (Профиль → «Нижние кнопки»). */
export default function Tab() {
  const { c, t } = useApp();
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top']}>
      <OfflineBar />
      <Feed header={<Txt kind="h1" style={{ paddingHorizontal: 16, paddingTop: 8, paddingBottom: 4 }}>{t('Лента')}</Txt>} />
    </SafeAreaView>
  );
}
