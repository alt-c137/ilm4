import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, FlatList, Pressable, RefreshControl, ScrollView, TextInput, View } from 'react-native';

import { shortDate } from '@/lib/hijri';
import { api } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Button, Empty, ErrorBox, Icon, Press, Screen, Sheet, Skeleton, Txt, type IconName } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type Th = { id: number; title: string; subject: string; other_id: number | null; avatar: string; preview: string; kind: string; mine: boolean; updated_at: string; unread: number; nikah: boolean; folder: string; context: string;
  room: '' | 'group' | 'channel'; author: string; muted: boolean; verified: boolean; read: boolean; online?: boolean };
type Folder = { key: string; name: string; n: number; unread: number };

const KIND_ICON: Record<string, IconName> = { photo: 'image', video: 'videocam', voice: 'mic', circle: 'aperture', file: 'document-attach', system: 'call' };

/** Время в списке, как в мессенджерах: сегодня — «14:05», раньше — дата. */
function when(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  if (d.toDateString() === now.toDateString()) return `${p(d.getHours())}:${p(d.getMinutes())}`;
  return shortDate(iso);
}

export default function Chats() {
  const { c, t, user } = useApp();
  const { data, loading, error, reload } = useFetch<{ items: Th[]; folders: Folder[]; support: boolean; can_group: boolean; can_channel: boolean; channels: boolean }>(user ? '/chat/' : null);
  const [folder, setFolder] = useState('');
  const [q, setQ] = useState('');
  const [menu, setMenu] = useState(false);
  const folders = data?.folders ?? [];
  const current = folders.some((x) => x.key === folder) ? folder : '';
  const needle = q.trim().toLowerCase();
  const items = (data?.items ?? []).filter((th) => (!current || th.folder === current)
    && (!needle || th.title.toLowerCase().includes(needle) || th.subject.toLowerCase().includes(needle)));
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
    <Screen title={t('Чаты')} scroll={false} padded={false}
      right={
        <Pressable onPress={() => setMenu(true)} hitSlop={10} accessibilityLabel={t('Ещё')} style={{ padding: 4 }}>
          <Icon name="ellipsis-vertical" size={22} color={c.ink} />
        </Pressable>}>
      {/* список рисует только то, что на экране: сотни чатов листаются так же легко, как десять */}
      <FlatList
        data={items}
        keyExtractor={(th) => String(th.id)}
        initialNumToRender={12} windowSize={9} removeClippedSubviews
        contentContainerStyle={{ paddingHorizontal: 12, paddingBottom: 96 }}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={loading && !!data} onRefresh={reload} tintColor={c.accent} />}
        ItemSeparatorComponent={() => <View style={{ height: 0.5, backgroundColor: c.line, marginLeft: 78 }} />}
        ListHeaderComponent={
          <View style={{ gap: 10, paddingBottom: 8 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, height: 42, borderRadius: 21, backgroundColor: c.card, borderWidth: 1, borderColor: c.line, paddingHorizontal: 14 }}>
              <Icon name="search" size={17} color={c.inkSoft} />
              <TextInput value={q} onChangeText={setQ} placeholder={t('Поиск')} placeholderTextColor={c.inkSoft} returnKeyType="search"
                style={{ flex: 1, fontSize: 16, color: c.ink, paddingVertical: 0 }} />
              {q ? <Pressable onPress={() => setQ('')} hitSlop={10}><Icon name="close-circle" size={17} color={c.inkSoft} /></Pressable> : null}
            </View>
            {folders.length > 1 ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
                {chip('', t('Все'), folders.reduce((n, x) => n + x.unread, 0))}
                {folders.map((x) => chip(x.key, x.name, x.unread))}
              </ScrollView>
            ) : null}
          </View>}
        ListEmptyComponent={!data ? (loading ? <Skeleton rows={8} /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : (
          <Empty icon="chatbubbles-outline" title={q ? t('Ничего не нашлось') : t('Пока нет диалогов')}
            text={t('Найдите человека по @имени или по номеру — и сразу пишите.')}
            action={<Button small kind="soft" title={t('Найти человека')} onPress={() => router.push('/chat/people')} />} />
        )}
        renderItem={({ item: th }) => (
          <Press onPress={() => router.push(`/chat/${th.id}`)} scale={0.985}
            style={{ flexDirection: 'row', gap: 12, alignItems: 'center', paddingVertical: 10, paddingHorizontal: 6, borderRadius: 16 }}>
            <View>
              <Avatar uri={th.avatar} name={th.title} size={56} hue={th.other_id ?? th.id} online={th.online} />
              {th.nikah ? <View style={{ position: 'absolute', right: -2, bottom: -2, backgroundColor: c.bg, borderRadius: 11, padding: 3 }}><Icon name="heart" size={14} color="#e0457b" /></View> : null}
              {th.room ? <View style={{ position: 'absolute', right: -2, bottom: -2, backgroundColor: c.bg, borderRadius: 11, padding: 3 }}>
                <Icon name={th.room === 'channel' ? 'megaphone' : 'people'} size={13} color={c.accent} /></View> : null}
            </View>
            <View style={{ flex: 1, gap: 3 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Txt style={{ flexShrink: 1, fontSize: 16.5, fontWeight: '700' }} numberOfLines={1}>{th.title}</Txt>
                {th.verified ? <Icon name="checkmark-circle" size={15} color={c.accent} /> : null}
                {th.muted ? <Icon name="notifications-off" size={13} color={c.inkSoft} /> : null}
                <View style={{ flex: 1 }} />
                {th.mine && !th.room && th.preview ? <Icon name={th.read ? 'checkmark-done' : 'checkmark'} size={16} color={th.read ? c.accent : c.inkSoft} /> : null}
                <Txt kind="small" color={th.unread ? c.accent : c.inkSoft} style={{ fontWeight: th.unread ? '700' : '400' }}>{when(th.updated_at)}</Txt>
              </View>
              {th.subject && !th.room ? <Txt kind="small" numberOfLines={1} color={c.accentD} style={{ fontWeight: '600' }}>{th.subject}</Txt> : null}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
                {th.mine ? <Txt kind="small" color={c.accentD}>{t('Вы: ').trim()}</Txt> : th.author ? <Txt kind="small" color={c.accentD} numberOfLines={1} style={{ maxWidth: 110 }}>{th.author}:</Txt> : null}
                {KIND_ICON[th.kind] ? <Icon name={KIND_ICON[th.kind]} size={14} color={c.inkSoft} /> : null}
                <Txt style={{ flex: 1, fontSize: 14.5, color: c.inkSoft }} numberOfLines={1}>{th.preview || t('Нет сообщений')}</Txt>
                {th.unread ? (
                  <View style={{ minWidth: 22, height: 22, paddingHorizontal: 6, borderRadius: 11, backgroundColor: th.muted ? c.inkSoft : c.accent, alignItems: 'center', justifyContent: 'center' }}>
                    <Txt kind="small" color="#fff" style={{ fontSize: 12, fontWeight: '800' }}>{th.unread > 99 ? '99+' : th.unread}</Txt>
                  </View>
                ) : null}
              </View>
            </View>
          </Press>
        )}
      />
      <Sheet open={menu} onClose={() => setMenu(false)} items={[
        ...(data?.can_group ? [{ icon: 'people-outline' as const, title: t('Создать группу'), onPress: () => router.push({ pathname: '/chat/new', params: { kind: 'group' } }) }] : []),
        ...(data?.can_channel ? [{ icon: 'megaphone-outline' as const, title: t('Создать канал'), onPress: () => router.push({ pathname: '/chat/new', params: { kind: 'channel' } }) }] : []),
        ...(data?.channels ? [{ icon: 'search-outline' as const, title: t('Каналы и группы'), onPress: () => router.push('/chat/channels') }] : []),
        ...(data?.support ? [{ icon: 'help-buoy-outline' as const, title: t('Поддержка ilm4'), onPress: support }] : []),
        { icon: 'image-outline' as const, title: t('Фон чата'), onPress: () => router.push('/chat-look') },
      ]} />
      {/* круглая кнопка «написать» — как в Telegram */}
      <Press onPress={() => router.push('/chat/people')} haptic scale={0.92} accessibilityRole="button"
        style={{ position: 'absolute', right: 16, bottom: 18, width: 58, height: 58, borderRadius: 29, backgroundColor: c.accent, alignItems: 'center', justifyContent: 'center',
          shadowColor: c.accent, shadowOpacity: 0.45, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 6 }}>
        <Icon name="create" size={25} color="#fff" />
      </Press>
    </Screen>
  );
}
