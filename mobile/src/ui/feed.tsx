/**
 * Лента — как во ВКонтакте: сторис сверху, «Что у вас нового?», вкладки «Для вас» / «Подписки», карточки записей,
 * постов каналов и публикаций разделов; лайк, комментарии, «поделиться», просмотр фото на весь экран.
 * Один компонент — для вкладки «Лента», для переключателя на главной и для стены в профиле.
 */
import * as Haptics from 'expo-haptics';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { memo, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Alert, FlatList, Modal, Pressable, RefreshControl, ScrollView, Share, Text, useWindowDimensions, View } from 'react-native';
import Animated, { FadeIn, useAnimatedStyle, useSharedValue, withSequence, withSpring, withTiming } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, ApiError, authHeaders } from '@/lib/api';
import { openSiteUrl } from '@/lib/links';
import { useApp } from '@/state/app';

import { AdCard, Avatar, Empty, Icon, Sheet, Skeleton, toast, Txt, type AdData } from './kit';
import { PhotoViewer } from './photo-viewer';

export type Who = { id?: number; room?: number; name: string; avatar: string; handle: string; verified: boolean; hue: number };
export type Item = {
  key: string; kind: string; label: string; id: number; author: Who | null; title: string; text: string;
  images: { url: string; auth?: boolean }[]; price: string; url: string; web: string; created: string;
  likes: number; liked: boolean; saved?: boolean; comments: number; reposts?: number; views?: number; mine?: boolean; privacy?: string; edited?: boolean;
  repost?: { id: number; author: Who; text: string; created: string; images: { url: string }[] } | null;
  channel_comments?: boolean; comments_count?: number;
};
type Story = { id: number; kind: string; url: string; caption: string; created: string; seen: boolean };
type StoryGroup = { author: Who; items: Story[]; seen: boolean; mine: boolean };

/** «5 мин», «2 ч», «вчера», «3 окт» — как в соцсетях. */
export function ago(iso: string, t: (s: string, v?: Record<string, string | number>) => string, lang: string) {
  const d = new Date(iso);
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return t('только что');
  if (s < 3600) return t('{n} мин', { n: Math.floor(s / 60) });
  if (s < 86400) return t('{n} ч', { n: Math.floor(s / 3600) });
  if (s < 172800) return t('вчера');
  return d.toLocaleDateString(lang === 'en' ? 'en-US' : lang === 'uz' ? 'uz-UZ' : 'ru-RU', { day: 'numeric', month: 'short' });
}

function Grid({ images, onOpen }: { images: { url: string; auth?: boolean }[]; onOpen: (i: number) => void }) {
  const { c } = useApp();
  const { width } = useWindowDimensions();
  const w = width - 24;
  const src = (im: { url: string; auth?: boolean }) => ({ uri: im.url, headers: im.auth ? authHeaders() : undefined });
  if (!images.length) return null;
  if (images.length === 1) {
    return (
      <Pressable onPress={() => onOpen(0)}>
        <Image source={src(images[0])} style={{ width: w, height: w * 0.75, borderRadius: 14, backgroundColor: c.card2 }} contentFit="cover" transition={150} />
      </Pressable>
    );
  }
  const cols = images.length === 2 || images.length === 4 ? 2 : 3;
  const size = (w - (cols - 1) * 3) / cols;
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 3, borderRadius: 14, overflow: 'hidden' }}>
      {images.slice(0, 9).map((im, i) => (
        <Pressable key={`${im.url}${i}`} onPress={() => onOpen(i)}>
          <Image source={src(im)} style={{ width: size, height: size, backgroundColor: c.card2 }} contentFit="cover" transition={150} />
          {i === 8 && images.length > 9 ? (
            <View style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(10,12,22,0.5)', alignItems: 'center', justifyContent: 'center' }}>
              <Txt color="#fff" style={{ fontSize: 22, fontWeight: '800' }}>+{images.length - 9}</Txt>
            </View>
          ) : null}
        </Pressable>
      ))}
    </View>
  );
}

function openAuthor(a: Who | null) {
  if (!a) return;
  if (a.room) router.push(`/chat/${a.room}`);
  else if (a.id) router.push(`/user/${a.id}`);
}

export const FeedCard = memo(function FeedCard({ x, onChange, onRemove }: {
  x: Item; onChange: (x: Item) => void; onRemove: (key: string) => void;
}) {
  const { c, t, lang, user } = useApp();
  const [full, setFull] = useState(false);
  const [viewer, setViewer] = useState<{ list: { url: string }[]; i: number; auth: boolean } | null>(null);
  const [menu, setMenu] = useState(false);
  const [share, setShare] = useState(false);
  const long = x.text.length > 420;
  const pop = useSharedValue(1);
  const popStyle = useAnimatedStyle(() => ({ transform: [{ scale: pop.get() }] }));
  const like = async () => {
    if (!user) return router.push('/login');
    Haptics.selectionAsync().catch(() => {});
    if (!x.liked) pop.set(withSequence(withTiming(1.35, { duration: 110 }), withSpring(1, { damping: 6, stiffness: 260 })));
    onChange({ ...x, liked: !x.liked, likes: x.likes + (x.liked ? -1 : 1) });
    try {
      const r = await api<{ liked: boolean; likes: number }>('/feed/like/', { body: { target: x.key } });
      onChange({ ...x, liked: r.liked, likes: r.likes });
    } catch (e) {
      onChange(x);
      Alert.alert((e as ApiError).message);
    }
  };
  const keep = async () => {
    if (!user) return router.push('/login');
    Haptics.selectionAsync().catch(() => {});
    onChange({ ...x, saved: !x.saved });
    try {
      const r = await api<{ saved: boolean }>('/feed/save/', { body: { target: x.key } });
      onChange({ ...x, saved: r.saved });
      // как в Telegram: коротко говорим, куда это легло, и даём туда перейти
      if (r.saved) toast(t('Сохранено'), { label: t('Открыть'), onPress: () => router.push('/feed/saved') });
    } catch (e) {
      onChange(x);
      Alert.alert((e as ApiError).message);
    }
  };
  const askRepost = () => {
    if (!user) return router.push('/login');
    Alert.alert(t('Сделать репост на свою стену?'), undefined, [{ text: t('Отмена'), style: 'cancel' }, { text: t('Репост'), onPress: repost }]);
  };
  const comments = () => {
    if (x.kind === 'channel') {
      if (x.channel_comments && x.author?.room) router.push({ pathname: '/chat/post/[id]', params: { id: String(x.id), thread: String(x.author.room) } });
      return;
    }
    router.push({ pathname: '/feed/comments', params: { target: x.key } });
  };
  const remove = () => Alert.alert(t('Удалить запись?'), undefined, [
    { text: t('Отмена'), style: 'cancel' },
    { text: t('Удалить'), style: 'destructive', onPress: async () => {
      try {
        await api(`/feed/post/${x.id}/delete/`, { body: {} });
        onRemove(x.key);
      } catch (e) {
        Alert.alert((e as ApiError).message);
      }
    } },
  ]);
  const repost = async () => {
    try {
      await api('/feed/new/', { body: { repost_of: x.id, text: '' } });
      onChange({ ...x, reposts: (x.reposts ?? 0) + 1 });
      Alert.alert(t('Запись появилась на вашей стене'));
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const btn = (icon: any, n: number | undefined, onPress?: () => void, on = false, color?: string, anim = false) => (
    <Pressable onPress={onPress} disabled={!onPress} hitSlop={4}
      style={({ pressed }) => ({ flexDirection: 'row', alignItems: 'center', gap: 6, height: 36, paddingHorizontal: 12, borderRadius: 18,
        backgroundColor: on ? '#e5484d1f' : c.card2, opacity: pressed ? 0.7 : 1 })}>
      {anim ? <Animated.View style={popStyle}><Icon name={icon} size={19} color={color ?? (on ? '#e5484d' : c.inkSoft)} /></Animated.View>
        : <Icon name={icon} size={19} color={color ?? (on ? '#e5484d' : c.inkSoft)} />}
      {n ? <Txt style={{ fontSize: 14, fontWeight: '700' }} color={on ? '#e5484d' : c.inkSoft}>{n}</Txt> : null}
    </Pressable>
  );
  const who = x.author;
  return (
    <Animated.View entering={FadeIn.duration(220)} style={{ backgroundColor: c.card, paddingHorizontal: 12, paddingTop: 12, paddingBottom: 8, gap: 9, marginBottom: 8 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <Pressable onPress={() => openAuthor(who)} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          {who ? <Avatar uri={who.avatar} name={who.name} size={42} hue={who.hue} /> : (
            <View style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
              <Icon name={x.kind === 'news' ? 'newspaper' : 'location'} size={20} color={c.accentD} />
            </View>
          )}
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
              <Txt style={{ fontWeight: '700', fontSize: 15.5, flexShrink: 1 }} numberOfLines={1}>{who?.name ?? x.label}</Txt>
              {who?.verified ? <Icon name="checkmark-circle" size={15} color={c.accent} /> : null}
            </View>
            <Txt kind="small" numberOfLines={1}>{[who && x.label, ago(x.created, t, lang), x.privacy === 'close' ? t('близким') : '', x.edited ? t('изменено') : ''].filter(Boolean).join(' · ')}</Txt>
          </View>
        </Pressable>
        {x.mine ? <Pressable onPress={() => setMenu(true)} hitSlop={10} style={{ padding: 4 }}><Icon name="ellipsis-horizontal" size={20} color={c.inkSoft} /></Pressable> : null}
      </View>
      {x.title ? <Pressable onPress={() => openSiteUrl(x.web)}><Txt style={{ fontSize: 17, fontWeight: '800', lineHeight: 22 }}>{x.title}</Txt></Pressable> : null}
      {x.text ? (
        <Pressable onPress={() => long && setFull(true)} disabled={!long || full}>
          <Text style={{ fontSize: 15.5, lineHeight: 22, color: c.ink }} numberOfLines={long && !full ? 7 : undefined}>{x.text}</Text>
          {long && !full ? <Txt color={c.accentD} style={{ fontWeight: '700', marginTop: 2 }}>{t('Показать полностью')}</Txt> : null}
        </Pressable>
      ) : null}
      {x.price ? <View style={{ alignSelf: 'flex-start', backgroundColor: c.accentSoft, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 }}><Txt color={c.accentD} style={{ fontWeight: '800' }}>{x.price}</Txt></View> : null}
      <Grid images={x.images} onOpen={(i) => setViewer({ list: x.images, i, auth: !!x.images[0]?.auth })} />
      {x.repost ? (
        <View style={{ borderLeftWidth: 3, borderLeftColor: c.accent, paddingLeft: 10, gap: 6 }}>
          <Pressable onPress={() => openAuthor(x.repost!.author)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Avatar uri={x.repost.author.avatar} name={x.repost.author.name} size={30} hue={x.repost.author.hue} />
            <Txt style={{ fontWeight: '700' }}>{x.repost.author.name}</Txt>
            <Txt kind="small">{ago(x.repost.created, t, lang)}</Txt>
          </Pressable>
          {x.repost.text ? <Text style={{ fontSize: 15, lineHeight: 21, color: c.ink }}>{x.repost.text}</Text> : null}
          <Grid images={x.repost.images} onOpen={(i) => setViewer({ list: x.repost!.images, i, auth: false })} />
        </View>
      ) : null}
      {x.kind !== 'post' && x.kind !== 'channel' ? (
        <Pressable onPress={() => openSiteUrl(x.web)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start' }}>
          <Txt color={c.accentD} style={{ fontWeight: '700' }}>{t('Открыть')}</Txt><Icon name="chevron-forward" size={15} color={c.accentD} />
        </Pressable>
      ) : null}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, borderTopWidth: 0.5, borderTopColor: c.line, paddingTop: 7 }}>
        {btn(x.liked ? 'heart' : 'heart-outline', x.likes, like, x.liked, undefined, true)}
        {x.kind !== 'channel' || x.channel_comments ? btn('chatbubble-outline', x.kind === 'channel' ? x.comments_count : x.comments, comments) : null}
        {x.kind === 'post' ? btn('repeat', x.reposts, askRepost) : null}
        {btn('arrow-redo-outline', undefined, () => setShare(true))}
        <View style={{ flex: 1 }} />
        {x.views ? <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}><Icon name="eye-outline" size={16} color={c.inkSoft} /><Txt kind="small">{x.views}</Txt></View> : null}
        <Pressable onPress={keep} hitSlop={8} style={{ paddingHorizontal: 6 }} accessibilityLabel={t('Сохранить')}>
          <Icon name={x.saved ? 'bookmark' : 'bookmark-outline'} size={20} color={x.saved ? c.accent : c.inkSoft} />
        </Pressable>
      </View>
      {viewer ? (
        <PhotoViewer photos={viewer.list.map((p) => ({ url: p.url, name: who?.name }))} index={viewer.i} onClose={() => setViewer(null)}
          headers={viewer.auth ? authHeaders() : undefined} />
      ) : null}
      <Sheet open={menu} onClose={() => setMenu(false)} items={[
        { icon: 'trash-outline', danger: true, title: t('Удалить запись'), onPress: remove },
      ]} />
      <Sheet open={share} onClose={() => setShare(false)} title={t('Поделиться')} items={[
        ...(x.kind === 'post' && user ? [{ icon: 'repeat' as const, title: t('На своей стене'), onPress: repost }] : []),
        { icon: 'share-outline', title: t('Отправить…'), onPress: () => { Share.share({ message: x.web }); } },
      ]} />
    </Animated.View>
  );
});

/** Строка сторис: «Моя история» и кружки с цветным ободком у непросмотренных. */
function StoriesRow({ groups, onOpen, onAdd }: { groups: StoryGroup[]; onOpen: (i: number) => void; onAdd: () => void }) {
  const { c, t, user } = useApp();
  if (!user) return null;
  const ring = (seen: boolean, child: ReactNode) => (
    <View style={{ width: 66, height: 66, borderRadius: 33, padding: 3, backgroundColor: seen ? c.line : c.accent, alignItems: 'center', justifyContent: 'center' }}>
      <View style={{ borderRadius: 30, borderWidth: 3, borderColor: c.bg }}>{child}</View>
    </View>
  );
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 12, paddingHorizontal: 12, paddingVertical: 8 }}>
      <Pressable onPress={onAdd} style={{ alignItems: 'center', gap: 4, width: 70 }}>
        <View>
          {ring(true, <Avatar uri={user.avatar} name={user.name} size={54} hue={user.id} />)}
          <View style={{ position: 'absolute', right: 0, bottom: 0, width: 24, height: 24, borderRadius: 12, backgroundColor: c.accent, borderWidth: 3, borderColor: c.bg, alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="add" size={14} color="#fff" />
          </View>
        </View>
        <Txt kind="small" numberOfLines={1}>{t('Моя история')}</Txt>
      </Pressable>
      {groups.map((g, i) => (
        <Pressable key={g.author.id} onPress={() => onOpen(i)} style={{ alignItems: 'center', gap: 4, width: 70 }}>
          {ring(g.seen, <Avatar uri={g.author.avatar} name={g.author.name} size={54} hue={g.author.hue} />)}
          <Txt kind="small" numberOfLines={1}>{g.mine ? t('Вы') : g.author.name}</Txt>
        </Pressable>
      ))}
    </ScrollView>
  );
}

/** Просмотр сторис на весь экран: полоски сверху, касание справа — дальше, слева — назад. */
function StoryViewer({ groups, start, onClose, onSeen }: { groups: StoryGroup[]; start: number | null; onClose: () => void; onSeen: (id: number) => void }) {
  const { t } = useApp();
  const [pos, setPos] = useState<{ g: number; i: number } | null>(null);
  const [opened, setOpened] = useState<number | null>(null);
  if (start !== opened) {
    setOpened(start);
    if (start !== null) {
      const first = groups[start]?.items.findIndex((s) => !s.seen) ?? 0;
      setPos({ g: start, i: Math.max(0, first) });
    }
  }
  const g = pos ? groups[pos.g] : null;
  const s = g && pos ? g.items[pos.i] : null;
  const step = useCallback((by: number) => {
    setPos((p) => {
      if (!p) return p;
      let { g: gi, i } = p;
      i += by;
      if (i >= groups[gi].items.length) { gi += 1; i = 0; }
      if (i < 0) { gi -= 1; i = gi >= 0 ? groups[gi].items.length - 1 : 0; }
      if (gi < 0 || gi >= groups.length) { setTimeout(onClose, 0); return null; }
      return { g: gi, i };
    });
  }, [groups, onClose]);
  useEffect(() => {
    if (!s || !g) return;
    if (!g.mine && !s.seen) { api(`/feed/stories/${s.id}/view/`, { body: {} }).catch(() => {}); onSeen(s.id); }
    const timer = setTimeout(() => step(1), 6000);
    return () => clearTimeout(timer);
  }, [s, g, step, onSeen]);
  const viewers = async () => {
    if (!s) return;
    try {
      const r = await api<{ items: { name: string; reaction: string }[] }>(`/feed/stories/${s.id}/viewers/`, { body: {} });
      Alert.alert(t('Кто смотрел'), r.items.length ? r.items.map((v) => `${v.name} ${v.reaction}`).join('\n') : t('Пока никто не смотрел'));
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  if (start === null || !g || !s || !pos) return null;
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose} statusBarTranslucent>
      <SafeAreaView style={{ flex: 1, backgroundColor: '#000' }}>
        <View style={{ flexDirection: 'row', gap: 4, paddingHorizontal: 10, paddingTop: 8 }}>
          {g.items.map((it, i) => <View key={it.id} style={{ flex: 1, height: 3, borderRadius: 2, backgroundColor: i <= pos.i ? '#fff' : 'rgba(255,255,255,0.3)' }} />)}
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12 }}>
          <Avatar uri={g.author.avatar} name={g.author.name} size={34} hue={g.author.hue} />
          <Txt color="#fff" style={{ flex: 1, fontWeight: '700' }}>{g.author.name}</Txt>
          <Pressable onPress={onClose} hitSlop={12}><Icon name="close" size={28} color="#fff" /></Pressable>
        </View>
        <View style={{ flex: 1 }}>
          <Image source={{ uri: s.url }} style={{ flex: 1 }} contentFit="contain" />
          <Pressable onPress={() => step(-1)} style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '35%' }} />
          <Pressable onPress={() => step(1)} style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: '65%' }} />
        </View>
        {s.caption ? <Txt color="#fff" style={{ textAlign: 'center', padding: 14, fontSize: 16 }}>{s.caption}</Txt> : null}
        {g.mine ? (
          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 10, paddingBottom: 14 }}>
            <Pressable onPress={viewers} style={{ borderRadius: 999, paddingHorizontal: 16, paddingVertical: 10, backgroundColor: 'rgba(255,255,255,0.16)' }}>
              <Txt color="#fff" style={{ fontWeight: '700' }}>{t('Кто смотрел')}</Txt>
            </Pressable>
          </View>
        ) : null}
      </SafeAreaView>
    </Modal>
  );
}

/** Сохранённое не из записей (объявление, новость, пост канала): заголовок, пара строк и переход. */
function BriefCard({ x, onRemove }: { x: Item; onRemove: (key: string) => void }) {
  const { c, t } = useApp();
  const drop = async () => {
    onRemove(x.key);
    try { await api('/feed/save/', { body: { target: x.key } }); } catch { /* останется в списке до обновления */ }
  };
  return (
    <Pressable onPress={() => openSiteUrl(x.web)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: c.card, padding: 14, marginBottom: 8 }}>
      <View style={{ flex: 1, gap: 3 }}>
        <Txt style={{ fontWeight: '700', fontSize: 16 }} numberOfLines={2}>{x.title}</Txt>
        {x.text ? <Txt kind="muted" numberOfLines={2}>{x.text}</Txt> : null}
      </View>
      <Pressable onPress={drop} hitSlop={10} accessibilityLabel={t('Убрать из сохранённого')}><Icon name="bookmark" size={22} color={c.accent} /></Pressable>
    </Pressable>
  );
}

/** Лента целиком: header — то, что выше (например, переключатель «Главная · Лента»). */
export function Feed({ header, wallOf, saved }: { header?: ReactNode; wallOf?: number; saved?: boolean }) {
  const { c, t, user } = useApp();
  const [items, setItems] = useState<Item[] | null>(null);
  const [next, setNext] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [stories, setStories] = useState<StoryGroup[]>([]);
  const [storyAt, setStoryAt] = useState<number | null>(null);
  const [storiesOn, setStoriesOn] = useState(false);
  const [ad, setAd] = useState<AdData | null>(null);
  const loadingMore = useRef(false);

  const url = useCallback((before = '') => (saved ? '/feed/saved/' : wallOf ? `/feed/wall/${wallOf}/` : '/feed/') + (before ? `?before=${encodeURIComponent(before)}` : ''), [wallOf, saved]);
  const load = useCallback(async () => {
    setBusy(true);
    try {
      const r = await api<{ items: Item[]; next?: string; stories?: boolean; ad?: AdData | null }>(url());
      setItems(r.items);
      setAd(r.ad ?? null);
      setNext(r.next ?? '');
      setError('');
      if (!wallOf && !saved && r.stories && user) {
        setStoriesOn(true);
        api<{ items: StoryGroup[] }>('/feed/stories/').then((s) => setStories(s.items)).catch(() => {});
      }
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }, [url, wallOf, saved, user]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- загрузка ленты при открытии и смене вкладки
    load();
  }, [load]);
  const more = async () => {
    if (!next || loadingMore.current || wallOf || saved) return;
    loadingMore.current = true;
    try {
      const r = await api<{ items: Item[]; next: string }>(url(next));
      setItems((old) => [...(old ?? []), ...r.items.filter((x) => !(old ?? []).some((y) => y.key === x.key))]);
      setNext(r.next);
    } catch { /* следующая попытка — при следующей прокрутке */ } finally {
      loadingMore.current = false;
    }
  };
  const change = useCallback((x: Item) => setItems((old) => (old ?? []).map((y) => (y.key === x.key ? x : y))), []);
  const remove = useCallback((key: string) => setItems((old) => (old ?? []).filter((y) => y.key !== key)), []);
  const addStory = async () => {
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.85 });
    if (r.canceled || !r.assets[0]) return;
    const a = r.assets[0];
    const form = new FormData();
    form.append('photo', { uri: a.uri, name: a.fileName || 'story.jpg', type: a.mimeType || 'image/jpeg' } as any);
    try {
      await api('/feed/stories/new/', { form });
      const s = await api<{ items: StoryGroup[] }>('/feed/stories/');
      setStories(s.items);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const seen = useCallback((id: number) => setStories((old) => old.map((g) => {
    const items = g.items.map((s) => (s.id === id ? { ...s, seen: true } : s));
    return { ...g, items, seen: items.every((s) => s.seen) };
  })), []);

  const top = (
    <View style={{ backgroundColor: c.bg }}>
      {header}
      {!wallOf && !saved && storiesOn ? <StoriesRow groups={stories} onOpen={setStoryAt} onAdd={addStory} /> : null}
      {!wallOf && !saved && user ? (
        <Pressable onPress={() => router.push('/feed/new')} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: c.card, padding: 12, marginBottom: 8 }}>
          <Avatar uri={user.avatar} name={user.name} size={40} hue={user.id} />
          <Txt kind="muted" style={{ flex: 1, fontSize: 16 }}>{t('Что у вас нового?')}</Txt>
          <Icon name="image-outline" size={23} color={c.accent} />
        </Pressable>
      ) : null}
    </View>
  );
  return (
    <>
      <FlatList
        data={items ?? []}
        keyExtractor={(x) => x.key}
        renderItem={({ item, index }) => ((item as Item & { brief?: boolean }).brief ? <BriefCard x={item} onRemove={remove} /> : <><FeedCard x={item} onChange={saved ? (x) => (x.saved === false ? remove(x.key) : change(x)) : change} onRemove={remove} />
          {ad && index === 2 ? <AdCard ad={ad} onOpen={openSiteUrl} style={{ marginBottom: 8 }} /> : null}</>)}
        ListHeaderComponent={top}
        onEndReached={more}
        onEndReachedThreshold={0.6}
        initialNumToRender={5}
        windowSize={7}
        contentContainerStyle={{ paddingBottom: 40 }}
        refreshControl={<RefreshControl refreshing={busy && !!items} onRefresh={load} tintColor={c.accent} />}
        ListEmptyComponent={items === null ? (busy ? <View style={{ padding: 12 }}><Skeleton rows={4} image /></View> : <Empty icon="alert-circle-outline" title={error} />) : (
          saved ? <Empty icon="bookmark-outline" title={t('Здесь будет сохранённое')} text={t('Нажмите на флажок под записью или объявлением — и оно появится здесь.')} />
            : <Empty icon="newspaper-outline" title={wallOf ? t('Записей пока нет.') : t('Лента пока пустая')} />
        )}
        ListFooterComponent={next && !wallOf ? <Txt kind="small" style={{ textAlign: 'center', padding: 16 }}>{t('Загрузка…')}</Txt> : null}
      />
      <StoryViewer groups={stories} start={storyAt} onClose={() => setStoryAt(null)} onSeen={seen} />
    </>
  );
}
