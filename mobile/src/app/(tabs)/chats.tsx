/**
 * Список чатов — по механике Telegram: вкладки-папки (свои, с названиями и составом), «Все», архив строкой сверху,
 * закреплённые чаты, черновики, долгое нажатие — меню (закрепить, без звука, прочитано, архив, в папку, очистить,
 * удалить), свайп влево — в архив.
 */
import * as Haptics from 'expo-haptics';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, FlatList, Pressable, RefreshControl, ScrollView, TextInput, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { interpolate, useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';

import { shortDate } from '@/lib/hijri';
import { api } from '@/lib/api';
import { load, save } from '@/lib/storage';
import { useApp } from '@/state/app';
import { Avatar, Button, Empty, ErrorBox, Icon, Screen, Sheet, Skeleton, Txt, type IconName, type SheetItem } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type Th = { id: number; title: string; subject: string; other_id: number | null; avatar: string; preview: string; kind: string; mine: boolean; updated_at: string; unread: number; nikah: boolean; folder: string; context: string;
  room: '' | 'group' | 'channel'; author: string; muted: boolean; verified: boolean; read: boolean; online?: boolean;
  unread_mark?: boolean; pinned?: boolean; archived?: boolean; draft?: string; type?: string; saved?: boolean };
type Tab = { id: number; title: string; emoji: string; ids: number[]; pins: number[]; unread: number; unread_muted: number };
type Tabs = { folders: Tab[]; all: { ids: number[]; unread: number; unread_muted: number }; archive: { ids: number[]; unread: number; unread_muted: number; names: string[] } };
type Data = { items: Th[]; tabs?: Tabs; support: boolean; can_group: boolean; can_channel: boolean; channels: boolean };

const KIND_ICON: Record<string, IconName> = { photo: 'image', video: 'videocam', voice: 'mic', circle: 'aperture', file: 'document-attach', system: 'call', poll: 'stats-chart' };

/** Время в списке, как в мессенджерах: сегодня — «14:05», раньше — дата. */
function when(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  if (d.toDateString() === now.toDateString()) return `${p(d.getHours())}:${p(d.getMinutes())}`;
  return shortDate(iso);
}

/** Строка чата: свайп влево — в архив (или из архива), как в Telegram. */
function Row({ th, pinned, onOpen, onMenu, onSwipe, archiveMode }: {
  th: Th; pinned: boolean; onOpen: () => void; onMenu: () => void; onSwipe: () => void; archiveMode: boolean;
}) {
  const { c, t } = useApp();
  const x = useSharedValue(0);
  const swipe = Gesture.Pan().activeOffsetX(-16).failOffsetY([-10, 10]).runOnJS(true)
    .onUpdate((e) => { x.value = Math.max(-110, Math.min(0, e.translationX)); })
    .onEnd((e) => {
      if (e.translationX < -80) { Haptics.selectionAsync().catch(() => {}); onSwipe(); }
      x.value = withTiming(0, { duration: 180 });
    });
  const moved = useAnimatedStyle(() => ({ transform: [{ translateX: x.value }] }));
  const under = useAnimatedStyle(() => ({ opacity: interpolate(x.value, [-80, -20, 0], [1, 0.4, 0]) }));
  const badge = th.unread || th.unread_mark;
  return (
    <View>
      <Animated.View pointerEvents="none" style={[{ position: 'absolute', right: 0, top: 0, bottom: 0, width: 110, borderRadius: 16, backgroundColor: c.inkSoft,
        alignItems: 'center', justifyContent: 'center', gap: 2 }, under]}>
        <Icon name={archiveMode ? 'arrow-undo' : 'archive'} size={22} color="#fff" />
        <Txt kind="small" color="#fff" style={{ fontWeight: '700', fontSize: 12 }}>{archiveMode ? t('Вернуть') : t('В архив')}</Txt>
      </Animated.View>
      <GestureDetector gesture={swipe}>
        <Animated.View style={moved}>
          <Pressable onPress={onOpen} onLongPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {}); onMenu(); }} delayLongPress={380}
            style={({ pressed }) => ({ flexDirection: 'row', gap: 12, alignItems: 'center', paddingVertical: 10, paddingHorizontal: 6, borderRadius: 16,
              backgroundColor: pressed ? c.card2 : pinned ? `${c.card2}` : c.bg })}>
            <View>
              {th.saved ? (
                <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: '#5b76f7', alignItems: 'center', justifyContent: 'center' }}><Icon name="bookmark" size={25} color="#fff" /></View>
              ) : <Avatar uri={th.avatar} name={th.title} size={56} hue={th.other_id ?? th.id} online={th.online} />}
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
                <Txt kind="small" color={badge ? c.accent : c.inkSoft} style={{ fontWeight: badge ? '700' : '400' }}>{when(th.updated_at)}</Txt>
              </View>
              {th.subject && !th.room ? <Txt kind="small" numberOfLines={1} color={c.accentD} style={{ fontWeight: '600' }}>{th.subject}</Txt> : null}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
                {th.draft ? (
                  <Txt style={{ flex: 1, fontSize: 14.5, color: c.inkSoft }} numberOfLines={1}><Txt style={{ fontSize: 14.5, color: c.bad, fontWeight: '600' }}>{t('Черновик:')} </Txt>{th.draft}</Txt>
                ) : (
                  <>
                    {th.mine ? <Txt kind="small" color={c.accentD}>{t('Вы: ').trim()}</Txt> : th.author ? <Txt kind="small" color={c.accentD} numberOfLines={1} style={{ maxWidth: 110 }}>{th.author}:</Txt> : null}
                    {KIND_ICON[th.kind] ? <Icon name={KIND_ICON[th.kind]} size={14} color={c.inkSoft} /> : null}
                    <Txt style={{ flex: 1, fontSize: 14.5, color: c.inkSoft }} numberOfLines={1}>
                      {th.preview || (th.saved ? t('Заметки, ссылки и пересланное — только для вас') : t('Нет сообщений'))}</Txt>
                  </>
                )}
                {th.unread ? (
                  <View style={{ minWidth: 22, height: 22, paddingHorizontal: 6, borderRadius: 11, backgroundColor: th.muted ? c.inkSoft : c.accent, alignItems: 'center', justifyContent: 'center' }}>
                    <Txt kind="small" color="#fff" style={{ fontSize: 12, fontWeight: '800' }}>{th.unread > 99 ? '99+' : th.unread}</Txt>
                  </View>
                ) : th.unread_mark ? <View style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: th.muted ? c.inkSoft : c.accent }} />
                  : pinned ? <Icon name="pin" size={15} color={c.inkSoft} style={{ transform: [{ rotate: '40deg' }] }} /> : null}
              </View>
            </View>
          </Pressable>
        </Animated.View>
      </GestureDetector>
    </View>
  );
}

type Found = { people: { id: number; name: string; handle: string; avatar: string }[];
  rooms: { id: number; kind: string; title: string; avatar: string; members: number }[];
  spaces: { id: number; title: string; icon: string; members: number }[];
  messages: { id: number; thread: number; title: string | null; who: string; text: string; time: string }[] };

export default function Chats() {
  const { c, t, user } = useApp();
  const { data, setData, loading, error, reload } = useFetch<Data>(user ? '/chat/' : null);
  const [folder, setFolder] = useState<number | 'all' | 'archive'>('all');
  const [q, setQ] = useState('');
  // единый поиск, как в Telegram: свои чаты фильтруются сразу, сервер добавляет людей, каналы, сообщества и сообщения
  const [found, setFound] = useState<Found | null>(null);
  const findSeq = useRef(0);
  useEffect(() => {
    const text = q.trim(), my = ++findSeq.current;
    if (text.length < 2) return;
    const timer = setTimeout(() => {
      api<Found>(`/chat/find/?q=${encodeURIComponent(text)}`).then((r) => { if (my === findSeq.current) setFound(r); }).catch(() => {});
    }, 300);
    return () => clearTimeout(timer);
  }, [q]);
  const [menu, setMenu] = useState(false);
  const [rowMenu, setRowMenu] = useState<Th | null>(null);
  const [tabMenu, setTabMenu] = useState<Tab | null>(null);
  const [pickFolder, setPickFolder] = useState<Th | null>(null);
  const tabs = data?.tabs;
  const current = folder === 'archive' ? (tabs?.archive.ids.length ? 'archive' : 'all')
    : typeof folder === 'number' && !tabs?.folders.some((f) => f.id === folder) ? 'all' : folder;
  const tab = typeof current === 'number' ? tabs?.folders.find((f) => f.id === current) : undefined;

  // открытая вкладка запоминается, как в Telegram
  useEffect(() => {
    load<number | 'all' | null>('chats.folder', null).then((v) => { if (v !== null) setFolder(v); });
  }, []);
  const go = (key: number | 'all' | 'archive') => {
    setFolder(key);
    if (key !== 'archive') save('chats.folder', key);
    Haptics.selectionAsync().catch(() => {});
  };

  const needle = q.trim().toLowerCase();
  const all = data?.items ?? [];
  const allow = new Set(current === 'all' ? tabs?.all.ids ?? all.filter((x) => !x.archived).map((x) => x.id)
    : current === 'archive' ? tabs?.archive.ids ?? [] : tab?.ids ?? []);
  const pins = tab ? tab.pins : [];
  let items = needle ? all.filter((th) => th.title.toLowerCase().includes(needle) || th.subject.toLowerCase().includes(needle)) : all.filter((th) => allow.has(th.id));
  if (pins.length && !needle) {
    items = [...items].sort((a, b) => {
      const pa = pins.indexOf(a.id), pb = pins.indexOf(b.id);
      if (pa === -1 && pb === -1) return 0;
      if (pa === -1) return 1;
      if (pb === -1) return -1;
      return pa - pb;
    });
  }
  const isPinned = (th: Th) => (tab ? pins.includes(th.id) : current === 'all' && !!th.pinned);

  const support = async () => {
    try {
      const r = await api('/chat/support/', { body: {} });
      router.push(`/chat/${r.thread}`);
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };
  const saved = async () => {
    try {
      const r = await api('/chat/saved/', { body: {} });
      router.push(`/chat/${r.thread}`);
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };
  const act = async (th: Th, action: string, extra: Record<string, unknown> = {}) => {
    try {
      await api(`/chat/${th.id}/state/${action}/`, { body: extra });
      reload(true);
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };
  // мгновенный отклик: архив и закреп видны сразу, сервер догоняет
  const optimistic = (th: Th, part: Partial<Th>) => {
    if (!data) return;
    setData({ ...data, items: data.items.map((x) => (x.id === th.id ? { ...x, ...part } : x)),
      tabs: data.tabs && part.archived !== undefined ? {
        ...data.tabs,
        all: { ...data.tabs.all, ids: part.archived ? data.tabs.all.ids.filter((i) => i !== th.id) : [...data.tabs.all.ids, th.id] },
        archive: { ...data.tabs.archive, ids: part.archived ? [th.id, ...data.tabs.archive.ids] : data.tabs.archive.ids.filter((i) => i !== th.id) },
      } : data.tabs });
  };
  const archive = (th: Th) => {
    const on = !th.archived;
    optimistic(th, { archived: on, pinned: false });
    act(th, on ? 'archive' : 'unarchive');
  };
  const rowItems = (th: Th): SheetItem[] => {
    const pinnedHere = isPinned(th);
    const folderExtra = tab ? { folder: tab.id } : {};
    const unread = !!(th.unread || th.unread_mark);
    return [
      { icon: pinnedHere ? 'pin' : 'pin-outline', title: pinnedHere ? t('Открепить') : t('Закрепить'), onPress: () => act(th, pinnedHere ? 'unpin' : 'pin', folderExtra) },
      ...(!th.saved ? [{ icon: th.muted ? 'notifications-outline' as const : 'notifications-off-outline' as const, title: th.muted ? t('Включить звук') : t('Без звука'),
        onPress: () => act(th, th.muted ? 'unmute' : 'mute') }] : []),
      { icon: unread ? 'checkmark-done-outline' : 'mail-unread-outline', title: unread ? t('Пометить прочитанным') : t('Пометить непрочитанным'), onPress: () => act(th, unread ? 'read' : 'unread') },
      { icon: th.archived ? 'arrow-undo-outline' : 'archive-outline', title: th.archived ? t('Вернуть из архива') : t('В архив'), onPress: () => archive(th) },
      ...(tabs?.folders.length ? [{ icon: 'folder-open-outline' as const, title: t('Добавить в папку…'), onPress: () => setTimeout(() => setPickFolder(th), 350) }] : []),
      ...(tab && tab.ids.includes(th.id) ? [{ icon: 'folder-outline' as const, title: t('Убрать из этой папки'), onPress: () => act(th, 'folder_remove', { folder: tab.id }) }] : []),
      { icon: 'brush-outline', title: t('Очистить историю'), subtitle: t('Сообщения пропадут только у вас'), onPress: () => Alert.alert(t('Очистить историю?'), t('Сообщения пропадут только у вас.'), [
        { text: t('Отмена'), style: 'cancel' }, { text: t('Очистить'), style: 'destructive', onPress: () => act(th, 'clear') }]) },
      th.room ? { icon: 'exit-outline', danger: true, title: th.room === 'channel' ? t('Отписаться…') : t('Выйти из группы…'), onPress: () => router.push(`/chat/info/${th.id}`) }
        : { icon: 'trash-outline', danger: true, title: t('Удалить чат'), onPress: () => Alert.alert(t('Удалить чат?'), t('Он пропадёт из вашего списка; у собеседника переписка останется.'), [
          { text: t('Отмена'), style: 'cancel' }, { text: t('Удалить'), style: 'destructive', onPress: () => act(th, 'hide') }]) },
    ];
  };
  useFocusEffect(useCallback(() => { if (user) reload(true); }, [user, reload]));

  if (!user) {
    return (
      <Screen title={t('Чаты')}>
        <Empty icon="chatbubbles-outline" title={t('Войдите, чтобы переписываться')} text={t('Сообщения продавцам, работодателям и в никяхе — в одном месте.')}
          action={<Button title={t('Войти')} onPress={() => router.push('/login')} />} />
      </Screen>
    );
  }

  const tabBtn = (key: number | 'all', title: string, unread: number, muted: number, f?: Tab) => {
    const on = current === key;
    return (
      <Pressable key={String(key)} onPress={() => go(key)} onLongPress={f ? () => setTabMenu(f) : () => router.push('/chat/folders')} delayLongPress={380}
        style={{ paddingHorizontal: 12, paddingTop: 9, paddingBottom: 10, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Txt style={{ fontSize: 15, fontWeight: '700' }} color={on ? c.accent : c.inkSoft}>{title}</Txt>
        {unread || muted ? (
          <View style={{ minWidth: 20, height: 20, paddingHorizontal: 6, borderRadius: 10, backgroundColor: unread ? c.accent : c.inkSoft, opacity: unread ? 1 : 0.6, alignItems: 'center', justifyContent: 'center' }}>
            <Txt kind="small" color="#fff" style={{ fontSize: 11.5, fontWeight: '800' }}>{unread || muted}</Txt>
          </View>
        ) : null}
        {on ? <View style={{ position: 'absolute', left: 10, right: 10, bottom: 0, height: 3, borderTopLeftRadius: 3, borderTopRightRadius: 3, backgroundColor: c.accent }} /> : null}
      </Pressable>
    );
  };

  const foundRow = (key: string, title: string, sub: string, avatar: string, hue: number, onPress: () => void, time = '') => (
    <Pressable key={key} onPress={onPress} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 12, paddingVertical: 8 }}>
      <Avatar uri={avatar} name={title} size={48} hue={hue} />
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          <Txt style={{ flex: 1, fontWeight: '700', fontSize: 16 }} numberOfLines={1}>{title}</Txt>
          {time ? <Txt kind="small">{time}</Txt> : null}
        </View>
        <Txt kind="small" numberOfLines={1} style={{ fontSize: 14 }}>{sub}</Txt>
      </View>
    </Pressable>
  );
  const archiveRow = current === 'all' && !needle && tabs?.archive.ids.length ? (
    <Pressable onPress={() => go('archive')} style={({ pressed }) => ({ flexDirection: 'row', gap: 12, alignItems: 'center', paddingVertical: 8, paddingHorizontal: 6, borderRadius: 16, backgroundColor: pressed ? c.card2 : 'transparent' })}>
      <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: c.card2, alignItems: 'center', justifyContent: 'center' }}><Icon name="archive" size={24} color={c.inkSoft} /></View>
      <View style={{ flex: 1, gap: 3 }}>
        <Txt style={{ fontSize: 16.5, fontWeight: '700' }}>{t('Архив')}</Txt>
        <Txt style={{ fontSize: 14.5, color: c.inkSoft }} numberOfLines={1}>{tabs.archive.names.join(', ')}</Txt>
      </View>
      {tabs.archive.unread || tabs.archive.unread_muted ? (
        <View style={{ minWidth: 22, height: 22, paddingHorizontal: 6, borderRadius: 11, backgroundColor: tabs.archive.unread ? c.accent : c.inkSoft, alignItems: 'center', justifyContent: 'center' }}>
          <Txt kind="small" color="#fff" style={{ fontSize: 12, fontWeight: '800' }}>{tabs.archive.unread || tabs.archive.unread_muted}</Txt>
        </View>
      ) : null}
    </Pressable>
  ) : null;

  return (
    <Screen title={current === 'archive' ? t('Архив') : t('Чаты')} scroll={false} padded={false}
      right={
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
          {current === 'archive' ? (
            <Pressable onPress={() => go('all')} hitSlop={10} style={{ padding: 4 }}><Icon name="close" size={24} color={c.ink} /></Pressable>
          ) : null}
          <Pressable onPress={() => setMenu(true)} hitSlop={10} accessibilityLabel={t('Ещё')} style={{ padding: 4 }}>
            <Icon name="ellipsis-vertical" size={22} color={c.ink} />
          </Pressable>
        </View>}>
      {/* список рисует только то, что на экране: сотни чатов листаются так же легко, как десять */}
      <FlatList
        data={items}
        keyExtractor={(th) => String(th.id)}
        initialNumToRender={12} windowSize={9}
        contentContainerStyle={{ paddingHorizontal: 12, paddingBottom: 96 }}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={loading && !!data} onRefresh={reload} tintColor={c.accent} />}
        ItemSeparatorComponent={() => <View style={{ height: 0.5, backgroundColor: c.line, marginLeft: 78 }} />}
        ListHeaderComponent={
          <View style={{ gap: 6, paddingBottom: 6 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, height: 42, borderRadius: 21, backgroundColor: c.card, borderWidth: 1, borderColor: c.line, paddingHorizontal: 14 }}>
              <Icon name="search" size={17} color={c.inkSoft} />
              <TextInput value={q} onChangeText={setQ} placeholder={t('Поиск')} placeholderTextColor={c.inkSoft} returnKeyType="search"
                style={{ flex: 1, fontSize: 16, color: c.ink, paddingVertical: 0 }} />
              {q ? <Pressable onPress={() => setQ('')} hitSlop={10}><Icon name="close-circle" size={17} color={c.inkSoft} /></Pressable> : null}
            </View>
            {current !== 'archive' ? (
              tabs?.folders.length ? (
                <View style={{ borderBottomWidth: 0.5, borderBottomColor: c.line, marginHorizontal: -12 }}>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 6 }}>
                    {tabBtn('all', t('Все'), tabs.all.unread, tabs.all.unread_muted)}
                    {tabs.folders.map((f) => tabBtn(f.id, f.title, f.unread, f.unread_muted, f))}
                  </ScrollView>
                </View>
              ) : null
            ) : <Txt kind="small" style={{ paddingHorizontal: 4 }}>{t('Чат вернётся из архива сам, когда придёт новое сообщение (если у него не выключен звук).')}</Txt>}
            {archiveRow}
          </View>}
        ListFooterComponent={needle.length >= 2 && found ? (
          <View style={{ paddingBottom: 30 }}>
            {found.people.length + found.rooms.length + found.spaces.length ? <Txt kind="label" style={{ paddingHorizontal: 16, paddingTop: 12, paddingBottom: 4 }}>{t('Глобальный поиск')}</Txt> : null}
            {found.people.map((p) => foundRow(`p${p.id}`, p.name, p.handle ? `@${p.handle}` : '', p.avatar, p.id, () => router.push(`/user/${p.id}`)))}
            {found.rooms.map((r) => foundRow(`r${r.id}`, r.title, `${r.kind === 'channel' ? t('канал') : t('группа')} · ${r.members}`, r.avatar, r.id, () => router.push(`/chat/${r.id}`)))}
            {found.spaces.map((x) => foundRow(`s${x.id}`, x.title, `${t('сообщество')} · ${x.members}`, x.icon, x.id, () => router.push(`/space/${x.id}`)))}
            {found.messages.length ? <Txt kind="label" style={{ paddingHorizontal: 16, paddingTop: 12, paddingBottom: 4 }}>{t('Сообщения')}</Txt> : null}
            {found.messages.map((m) => foundRow(`m${m.id}`, m.title ?? t('Избранное'), (m.who ? `${m.who}: ` : '') + m.text, '', m.thread,
              () => router.push({ pathname: '/chat/[id]', params: { id: String(m.thread), at: String(m.id) } }), m.time))}
          </View>
        ) : null}
        ListEmptyComponent={!data ? (loading ? <Skeleton rows={8} /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : current !== 'all' && !needle ? (
          <Empty icon="folder-open-outline" title={t('В этой папке пока пусто')} text={t('Чаты попадают сюда по правилам папки. Изменить правила — «Настроить папки».')} />
        ) : (
          <Empty icon="chatbubbles-outline" title={q ? t('Ничего не нашлось') : t('Пока нет диалогов')}
            text={t('Найдите человека по @имени или по номеру — и сразу пишите.')}
            action={<Button small kind="soft" title={t('Найти человека')} onPress={() => router.push('/chat/people')} />} />
        )}
        renderItem={({ item: th }) => (
          <Row th={th} pinned={isPinned(th)} archiveMode={!!th.archived} onOpen={() => router.push(`/chat/${th.id}`)}
            onMenu={() => setRowMenu(th)} onSwipe={() => archive(th)} />
        )}
      />
      <Sheet open={menu} onClose={() => setMenu(false)} items={[
        ...(data?.can_group ? [{ icon: 'people-outline' as const, title: t('Создать группу'), onPress: () => router.push({ pathname: '/chat/new', params: { kind: 'group' } }) }] : []),
        ...(data?.can_channel ? [{ icon: 'megaphone-outline' as const, title: t('Создать канал'), onPress: () => router.push({ pathname: '/chat/new', params: { kind: 'channel' } }) }] : []),
        { icon: 'bookmark-outline' as const, title: t('Избранное'), onPress: saved },
        { icon: 'person-outline' as const, title: t('Контакты'), onPress: () => router.push('/chat/contacts') },
        { icon: 'folder-open-outline' as const, title: t('Папки с чатами'), onPress: () => router.push('/chat/folders') },
        ...(tabs?.archive.ids.length ? [{ icon: 'archive-outline' as const, title: t('Архив'), onPress: () => go('archive') }] : []),
        ...(data?.channels ? [{ icon: 'search-outline' as const, title: t('Каналы и группы'), onPress: () => router.push('/chat/channels') }] : []),
        ...(data?.support ? [{ icon: 'help-buoy-outline' as const, title: t('Поддержка ilm4'), onPress: support }] : []),
        { icon: 'image-outline' as const, title: t('Фон чата'), onPress: () => router.push('/chat-look') },
      ]} />
      <Sheet open={!!rowMenu} onClose={() => setRowMenu(null)} title={rowMenu?.title} items={rowMenu ? rowItems(rowMenu) : []} />
      <Sheet open={!!pickFolder} onClose={() => setPickFolder(null)} title={t('Добавить в папку')} items={[
        ...(tabs?.folders ?? []).map((f) => {
          const inside = !!pickFolder && f.ids.includes(pickFolder.id);
          return { icon: 'folder-outline' as const, title: f.title, on: inside,
            onPress: () => pickFolder && act(pickFolder, inside ? 'folder_remove' : 'folder_add', { folder: f.id }) };
        }),
        { icon: 'add' as const, title: t('Новая папка'), onPress: () => router.push('/chat/folder/new') },
      ]} />
      <Sheet open={!!tabMenu} onClose={() => setTabMenu(null)} title={tabMenu?.title} items={tabMenu ? [
        { icon: 'create-outline', title: t('Изменить папку'), onPress: () => router.push(`/chat/folder/${tabMenu.id}`) },
        { icon: 'reorder-three-outline', title: t('Порядок папок'), onPress: () => router.push('/chat/folders') },
        { icon: 'trash-outline', danger: true, title: t('Удалить папку'), onPress: () => Alert.alert(t('Удалить папку?'), t('Сами чаты останутся.'), [
          { text: t('Отмена'), style: 'cancel' },
          { text: t('Удалить'), style: 'destructive', onPress: async () => { await api(`/chat/folders/${tabMenu.id}/`, { method: 'DELETE' }).catch(() => {}); go('all'); reload(true); } }]) },
      ] : []} />
      {/* круглая кнопка «написать» — как в Telegram */}
      {current !== 'archive' ? (
        <Pressable onPress={() => router.push('/chat/people')} accessibilityRole="button" accessibilityLabel={t('Новое сообщение')}
          style={({ pressed }) => ({ position: 'absolute', right: 16, bottom: 18, width: 58, height: 58, borderRadius: 29, backgroundColor: c.accent, alignItems: 'center', justifyContent: 'center',
            transform: [{ scale: pressed ? 0.92 : 1 }], shadowColor: c.accent, shadowOpacity: 0.45, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 6 })}>
          <Icon name="create" size={25} color="#fff" />
        </Pressable>
      ) : null}
    </Screen>
  );
}
