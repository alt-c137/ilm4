import { router } from 'expo-router';
import { Pressable, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useApp } from '@/state/app';
import { Feed } from '@/ui/feed';
import { Icon, OfflineBar, Txt } from '@/ui/kit';

/** «Сохранённое» — всё, что человек отложил флажком в ленте: записи, объявления, новости, посты каналов. */
export default function SavedFeed() {
  const { c, t } = useApp();
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top']}>
      <OfflineBar />
      <Feed saved header={(
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 8, paddingTop: 6, paddingBottom: 8 }}>
          <Pressable onPress={() => router.back()} hitSlop={10} style={{ padding: 6 }}><Icon name="chevron-back" size={26} color={c.accent} /></Pressable>
          <Txt kind="h2">{t('Сохранённое')}</Txt>
        </View>
      )} />
    </SafeAreaView>
  );
}
