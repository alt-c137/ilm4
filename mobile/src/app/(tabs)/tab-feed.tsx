import { router } from 'expo-router';
import { Pressable, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useApp } from '@/state/app';
import { Feed } from '@/ui/feed';
import { Icon, OfflineBar, Txt } from '@/ui/kit';

/** «Лента» нижней кнопкой (Профиль → «Нижние кнопки»). Справа в шапке — сохранённое и новая запись. */
export default function Tab() {
  const { c, t, user } = useApp();
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top']}>
      <OfflineBar />
      <Feed header={<FeedHeader title={t('Лента')} signedIn={!!user} color={c.accent} labels={[t('Сохранённое'), t('Новая запись')]} />} />
    </SafeAreaView>
  );
}

function FeedHeader({ title, signedIn, color, labels }: { title: string; signedIn: boolean; color: string; labels: [string, string] }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 8, paddingBottom: 4 }}>
      <Txt kind="h1" style={{ flex: 1 }}>{title}</Txt>
      {signedIn ? (
        <View style={{ flexDirection: 'row', gap: 4 }}>
          <Pressable onPress={() => router.push('/feed/saved')} hitSlop={8} style={{ padding: 8 }} accessibilityLabel={labels[0]}><Icon name="bookmark-outline" size={24} color={color} /></Pressable>
          <Pressable onPress={() => router.push('/feed/new')} hitSlop={8} style={{ padding: 8 }} accessibilityLabel={labels[1]}><Icon name="add-circle-outline" size={26} color={color} /></Pressable>
        </View>
      ) : null}
    </View>
  );
}
