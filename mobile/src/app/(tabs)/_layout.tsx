import { Tabs } from 'expo-router';
import { View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApp } from '@/state/app';
import { Icon, type IconName } from '@/ui/kit';

function TabIcon({ name, color, focused }: { name: IconName; color: any; focused: boolean }) {
  return <Icon name={(focused ? name : `${name}-outline`) as IconName} size={24} color={color} />;
}

export default function TabsLayout() {
  const { c, t, moduleOn, config } = useApp();
  const chatOn = !config || moduleOn('chat');
  const insets = useSafeAreaInsets();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: c.accent,
        tabBarInactiveTintColor: c.inkSoft,
        tabBarStyle: { backgroundColor: c.card, borderTopColor: c.line, height: 62 + insets.bottom, paddingTop: 6, paddingBottom: 6 + insets.bottom },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600', lineHeight: 14 },
      }}>
      <Tabs.Screen name="index" options={{ title: t('Главная'), tabBarIcon: (p) => <TabIcon name="home" {...p} /> }} />
      <Tabs.Screen name="prayer" options={{ title: t('Намаз'), tabBarIcon: (p) => <TabIcon name="moon" {...p} /> }} />
      <Tabs.Screen name="services" options={{ title: t('Сервисы'), tabBarIcon: (p) => <TabIcon name="grid" {...p} /> }} />
      <Tabs.Screen name="chats" options={{ title: t('Чаты'), href: chatOn ? undefined : null,
        tabBarIcon: (p) => <TabIcon name="chatbubbles" {...p} /> }} />
      <Tabs.Screen name="me" options={{ title: t('Профиль'), tabBarIcon: (p) => <View><TabIcon name="person-circle" {...p} /></View> }} />
    </Tabs>
  );
}
