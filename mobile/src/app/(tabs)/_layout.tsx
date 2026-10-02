import * as Haptics from 'expo-haptics';
import { Tabs } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApp, type TabKey } from '@/state/app';
import { Icon, type IconName } from '@/ui/kit';

function TabIcon({ name, color, focused }: { name: IconName; color: any; focused: boolean }) {
  return <Icon name={(focused ? name : `${name}-outline`) as IconName} size={24} color={color} />;
}

/** Все экраны, которые можно держать внизу: файл вкладки, подпись, значок, раздел (выключен в админке — вкладки нет). */
export const TAB_INFO: Record<TabKey, { file: string; title: string; icon: IconName; module?: string }> = {
  home: { file: 'index', title: 'Главная', icon: 'home' },
  prayer: { file: 'prayer', title: 'Намаз', icon: 'moon', module: 'prayer' },
  services: { file: 'services', title: 'Сервисы', icon: 'grid' },
  chats: { file: 'chats', title: 'Чаты', icon: 'chatbubbles', module: 'chat' },
  tracker: { file: 'tracker', title: 'Трекер', icon: 'checkmark-circle', module: 'tracker' },
  nikah: { file: 'tab-nikah', title: 'Никях', icon: 'heart', module: 'nikah' },
  map: { file: 'tab-map', title: 'Карта', icon: 'location', module: 'map' },
  buy: { file: 'tab-buy', title: 'Маркет', icon: 'bag-handle', module: 'buy' },
  news: { file: 'tab-news', title: 'Новости', icon: 'newspaper', module: 'news' },
};

/**
 * Нижние кнопки выбирает сам человек (Профиль → «Нижние кнопки»). Экраны объявлены все и всегда —
 * меняется только, какие показаны и в каком порядке (скрытые открываются из «Сервисов» как обычно).
 */
export default function TabsLayout() {
  const { c, t, moduleOn, config, tabs } = useApp();
  const insets = useSafeAreaInsets();
  const on = (k: TabKey) => !TAB_INFO[k].module || !config || moduleOn(TAB_INFO[k].module!);
  const shown = tabs.filter(on);
  const rest = (Object.keys(TAB_INFO) as TabKey[]).filter((k) => !shown.includes(k));
  return (
    <Tabs
      screenListeners={{ tabPress: () => { Haptics.selectionAsync().catch(() => {}); } }}
      screenOptions={{
        animation: 'shift',          // вкладки сменяются плавным сдвигом, а не «щелчком»
        headerShown: false,
        tabBarActiveTintColor: c.accent,
        tabBarInactiveTintColor: c.inkSoft,
        tabBarStyle: { backgroundColor: c.card, borderTopColor: c.line, height: 62 + insets.bottom, paddingTop: 6, paddingBottom: 6 + insets.bottom },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600', lineHeight: 14 },
      }}>
      {[...shown, ...rest].map((k) => {
        const info = TAB_INFO[k];
        return (
          <Tabs.Screen key={k} name={info.file} options={{ title: t(info.title), href: shown.includes(k) ? undefined : null,
            tabBarIcon: (p) => <TabIcon name={info.icon} {...p} /> }} />
        );
      })}
      <Tabs.Screen name="me" options={{ title: t('Профиль'), tabBarIcon: (p) => <TabIcon name="person-circle" {...p} /> }} />
    </Tabs>
  );
}
