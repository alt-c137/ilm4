import * as Haptics from 'expo-haptics';
import { router, Tabs } from 'expo-router';
import { useEffect, useRef, type ComponentProps } from 'react';
import { Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';
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
  feed: { file: 'tab-feed', title: 'Лента', icon: 'albums', module: 'feed' },
  communities: { file: 'tab-communities', title: 'Сообщества', icon: 'people', module: 'communities' },
  jobs: { file: 'tab-jobs', title: 'Работа', icon: 'briefcase', module: 'jobs' },
  transport: { file: 'tab-trips', title: 'Попутчики', icon: 'car', module: 'transport' },
  forum: { file: 'tab-forum', title: 'Форум', icon: 'chatbox-ellipses', module: 'forum' },
  library: { file: 'tab-library', title: 'Книги', icon: 'library', module: 'library' },
};

/**
 * Нижние кнопки выбирает сам человек (Профиль → «Нижние кнопки»). Экраны объявлены все и всегда —
 * меняется только, какие показаны и в каком порядке (скрытые открываются из «Сервисов» как обычно).
 */
type BottomTabBarProps = Parameters<NonNullable<ComponentProps<typeof Tabs>['tabBar']>>[0];

/** Нижняя панель: до пяти кнопок — поровну на ширину экрана; больше — листается пальцем (как человеку удобно). */
function Bar({ state, descriptors, navigation, files }: BottomTabBarProps & { files: string[] }) {
  const { c } = useApp();
  const insets = useSafeAreaInsets();
  const win = useWindowDimensions();
  const routes = state.routes.filter((r) => files.includes(r.name));
  const width = routes.length > 5 ? Math.max(68, win.width / 5.4) : win.width / Math.max(1, routes.length);
  const items = routes.map((route) => {
    const focused = state.routes[state.index]?.key === route.key;
    const { options } = descriptors[route.key];
    const color = focused ? c.accent : c.inkSoft;
    const press = () => {
      Haptics.selectionAsync().catch(() => {});
      const e = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
      if (!focused && !e.defaultPrevented) navigation.navigate(route.name);
    };
    return (
      <Pressable key={route.key} onPress={press} accessibilityRole="button" accessibilityState={focused ? { selected: true } : {}}
        style={{ width, alignItems: 'center', justifyContent: 'center', gap: 2, paddingTop: 6 }}>
        {options.tabBarIcon?.({ focused, color, size: 24 })}
        <Text numberOfLines={1} style={{ color, fontSize: routes.length > 4 ? 10 : 11, fontWeight: '600', lineHeight: 14 }}>{options.title}</Text>
      </Pressable>
    );
  });
  const style = { backgroundColor: c.card, borderTopWidth: 0.5, borderTopColor: c.line, height: 62 + insets.bottom, paddingBottom: 6 + insets.bottom };
  if (routes.length <= 5) return <View style={[style, { flexDirection: 'row' }]}>{items}</View>;
  return <View style={style}><ScrollView horizontal showsHorizontalScrollIndicator={false}>{items}</ScrollView></View>;
}

export default function TabsLayout() {
  const { c, t, moduleOn, config, tabs } = useApp();
  const on = (k: TabKey) => !TAB_INFO[k].module || !config || moduleOn(TAB_INFO[k].module!);
  const shown = tabs.filter(on);
  const rest = (Object.keys(TAB_INFO) as TabKey[]).filter((k) => !shown.includes(k));
  const files = [...shown.map((k) => TAB_INFO[k].file), 'me'];
  // стартовый экран — первая кнопка: убрал «Главную» с первого места — приложение открывается, например, сразу чатами
  const started = useRef(false);
  const first = shown[0];
  useEffect(() => {
    if (started.current || !config || !first) return;
    started.current = true;
    if (first !== 'home') router.replace(`/${TAB_INFO[first].file}` as never);
  }, [config, first]);
  return (
    <Tabs
      tabBar={(props) => <Bar {...props} files={files} />}
      screenOptions={{
        animation: 'shift',          // вкладки сменяются плавным сдвигом, а не «щелчком»
        headerShown: false,
        tabBarActiveTintColor: c.accent,
        tabBarInactiveTintColor: c.inkSoft,
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
