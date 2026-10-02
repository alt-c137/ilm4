import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Pressable, ScrollView, View } from 'react-native';

import { shortDate } from '@/lib/hijri';
import { api } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Badge, Button, Empty, ErrorBox, Icon, Loading, Screen, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type Th = { id: number; title: string; subject: string; other_id: number | null; avatar: string; preview: string; kind: string; mine: boolean; updated_at: string; unread: number; nikah: boolean; folder: string; context: string };
type Folder = { key: string; name: string; n: number; unread: number };

const KIND_ICON: Record<string, string> = { photo: '📷 ', video: '🎬 ', voice: '🎤 ', circle: '⭕ ', file: '📎 ' };

export default function Chats() {
  const { c, t, user } = useApp();
  const { data, loading, error, reload } = useFetch<{ items: Th[]; folders: Folder[]; support: boolean }>(user ? '/chat/' : null);
  const [folder, setFolder] = useState('');
  const folders = data?.folders ?? [];
  const current = folders.some((x) => x.key === folder) ? folder : '';
  const items = (data?.items ?? []).filter((th) => !current || th.folder === current);
  const support = async () => {
    try {
      const r = await api('/chat/support/', { body: {} });
      router.push(`/chat/${r.thread}`);
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };
  const chip = (key: string, name: string, unread: number) => (
    <Pressable key={key || 'all'} onPress={() => setFolder(key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 13, paddingVertical: 7,
      borderRadius: 999, backgroundColor: current === key ? c.accent : c.card2 }}>
      <Txt kind="small" color={current === key ? '#fff' : c.inkSoft} style={{ fontWeight: '700' }}>{name}</Txt>
      {unread ? <View style={{ minWidth: 18, paddingHorizontal: 5, borderRadius: 9, backgroundColor: current === key ? '#fff' : c.accent, alignItems: 'center' }}>
        <Txt kind="small" color={current === key ? c.accentD : '#fff'} style={{ fontSize: 11, fontWeight: '800' }}>{unread}</Txt></View> : null}
    </Pressable>
  );
  useFocusEffect(useCallback(() => { if (user) reload(true); }, [user, reload]));

  if (!user) {
    return (
      <Screen title={t('Чаты')}>
        <Empty icon="chatbubbles-outline" title={t('Войдите, чтобы переписываться')} text={t('Сообщения продавцам, работодателям и в никяхе — в одном месте.')}
          action={<Button title={t('Войти')} onPress={() => router.push('/login')} />} />
      </Screen>
    );
  }
  return (
    <Screen title={t('Чаты')} onRefresh={reload} refreshing={loading && !!data} padded={false}
      right={data?.support ? <Pressable onPress={support} hitSlop={10} accessibilityLabel={t('Поддержка ilm4')}><Icon name="help-buoy-outline" size={24} color={c.accent} /></Pressable> : undefined}>
      {folders.length > 1 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingHorizontal: 12, paddingBottom: 8 }}>
          {chip('', t('Все'), folders.reduce((n, x) => n + x.unread, 0))}
          {folders.map((x) => chip(x.key, x.name, x.unread))}
        </ScrollView>
      ) : null}
      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : !data.items.length ? (
        <Empty icon="chatbubbles-outline" title={t('Пока нет диалогов')} text={t('Напишите автору объявления — диалог появится здесь.')} />
      ) : null}
      <View style={{ paddingHorizontal: 12 }}>
        {items.map((th) => (
          <Pressable key={th.id} onPress={() => router.push(`/chat/${th.id}`)} style={({ pressed }) => ({
            flexDirection: 'row', gap: 12, alignItems: 'center', padding: 10, borderRadius: 18, backgroundColor: pressed ? c.card2 : 'transparent' })}>
            <View>
              <Avatar uri={th.avatar} name={th.title} size={52} hue={th.other_id ?? th.id} />
              {th.nikah ? <View style={{ position: 'absolute', right: -2, bottom: -2, backgroundColor: c.card, borderRadius: 10, padding: 2 }}><Icon name="heart" size={14} color="#e0457b" /></View> : null}
            </View>
            <View style={{ flex: 1, gap: 2 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Txt kind="h3" style={{ flex: 1 }} numberOfLines={1}>{th.title}</Txt>
                <Txt kind="small">{shortDate(th.updated_at)}</Txt>
              </View>
              {th.subject ? <Txt kind="small" numberOfLines={1} color={c.accentD}>{th.subject}</Txt> : null}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Txt kind="small" style={{ flex: 1 }} numberOfLines={1}>{th.mine ? t('Вы: ') : ''}{KIND_ICON[th.kind] ?? ''}{th.preview}</Txt>
                <Badge n={th.unread} />
              </View>
            </View>
          </Pressable>
        ))}
      </View>
    </Screen>
  );
}
