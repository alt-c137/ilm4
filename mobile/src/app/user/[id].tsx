import { Image } from 'expo-image';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Platform, Pressable, ScrollView, RefreshControl, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, ApiError, authHeaders, chatFileUrl } from '@/lib/api';
import { statusText, type Presence } from '@/lib/presence';
import { useApp, type SocialLink } from '@/state/app';
import { ErrorBox, Icon, Loading, OfflineBar, Press, Segmented, Sheet, Txt } from '@/ui/kit';
import { ChatFile } from '@/ui/media';
import { ProfileActions, ProfileHead, ProfileInfo, type Action } from '@/ui/profile';
import { FeedCard, type Item } from '@/ui/feed';
import { PhotoViewer } from '@/ui/photo-viewer';
import { useFetch } from '@/ui/useFetch';

type Pub = { id: number; type: string; title: string; subtitle: string; image: string };
type Profile = { id: number; me: boolean; name: string; handle: string; bio: string; city: string; avatar: string; verified: boolean; joined: string;
  presence: Presence; phone: string; links: SocialLink[]; close: boolean; contact?: boolean; blocked: boolean; blocked_any: boolean; thread: number | null; muted: boolean;
  chat: boolean; features: { calls?: boolean; video_calls?: boolean }; pubs: Pub[]; photos?: { id: number; url: string; date: string }[] };
type Media = { id: number; kind: string; file_name?: string; file_size?: number; mine?: boolean };
type Tab = 'wall' | 'pubs' | 'media' | 'files';
type Wall = { items: Item[]; following: boolean; followers?: number; follows?: number; posts?: number; counts_hidden?: boolean };

/** Профиль человека — как в Telegram: аватар, «в сети», Чат · Звук · Звонок · Видео, сведения, вкладки. */
export default function UserProfile() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { c, t, lang, moduleOn } = useApp();
  const feedOn = moduleOn('feed');
  const { width } = useWindowDimensions();
  const { data, setData, loading, error, reload } = useFetch<Profile>(`/users/${id}/`);
  const [tab, setTab] = useState<Tab | null>(null);
  const wall = useFetch<Wall>(feedOn ? `/feed/wall/${id}/` : null);
  const [menu, setMenu] = useState(false);
  const [photo, setPhoto] = useState<number | null>(null);
  const tabNow: Tab = tab ?? (feedOn ? 'wall' : 'pubs');
  const media = useFetch<{ items: Media[] }>(data?.thread && tabNow === 'media' ? `/chat/${data.thread}/media/?what=media` : null);
  const files = useFetch<{ items: Media[] }>(data?.thread && tabNow === 'files' ? `/chat/${data.thread}/media/?what=files` : null);
  useFocusEffect(useCallback(() => { reload(true); }, [reload]));

  const back = () => (router.canGoBack() ? router.back() : router.replace('/chats'));
  if (!data) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top']}>
        <Pressable onPress={back} hitSlop={12} style={{ padding: 12 }}><Icon name="chevron-back" size={27} color={c.accent} /></Pressable>
        {loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />}
      </SafeAreaView>
    );
  }

  const fail = (e: unknown) => Alert.alert((e as ApiError).message);
  const openChat = async (call?: 'audio' | 'video') => {
    try {
      const thread = data.thread ?? (await api<{ thread: number }>(`/users/${data.id}/chat/`, { body: {} })).thread;
      router.push(call ? { pathname: '/chat/[id]', params: { id: String(thread), call } } : `/chat/${thread}`);
    } catch (e) {
      fail(e);
    }
  };
  const mute = async () => {
    try {
      const thread = data.thread ?? (await api<{ thread: number }>(`/users/${data.id}/chat/`, { body: {} })).thread;
      const r = await api<{ muted: boolean }>(`/chat/${thread}/mute/`, { body: { on: !data.muted } });
      setData({ ...data, thread, muted: r.muted });
    } catch (e) {
      fail(e);
    }
  };
  const close = async () => {
    try {
      const r = await api<{ close: boolean }>(`/users/${data.id}/close/`, { body: { on: !data.close } });
      setData({ ...data, close: r.close });
    } catch (e) {
      fail(e);
    }
  };
  const block = async () => {
    try {
      await api('/block/', { body: { user_id: data.id, unblock: data.blocked } });
      reload(true);
    } catch (e) {
      fail(e);
    }
  };

  const actions: Action[] = data.me ? [
    { icon: 'create-outline', label: t('Изменить'), onPress: () => router.push('/profile-edit') },
    { icon: 'lock-closed-outline', label: t('Приватность'), onPress: () => router.push('/privacy') },
    { icon: 'document-text-outline', label: t('Публикации'), onPress: () => router.push('/my') },
  ] : data.chat && !data.blocked_any ? [
    { icon: 'chatbubble', label: t('Чат'), onPress: () => openChat() },
    { icon: data.muted ? 'notifications-off' : 'notifications', label: data.muted ? t('Без звука') : t('Звук'), onPress: mute, off: data.muted },
    ...(data.features.calls && Platform.OS !== 'web' ? [{ icon: 'call' as const, label: t('Звонок'), onPress: () => openChat('audio') }] : []),
    ...(data.features.video_calls && Platform.OS !== 'web' ? [{ icon: 'videocam' as const, label: t('Видео'), onPress: () => openChat('video') }] : []),
  ] : [];
  const cell = Math.floor((width - 32 - 6) / 3);
  const follow = async () => {
    if (!wall.data) return;
    try {
      const r = await api<{ following: boolean; followers: number }>(`/users/${data.id}/follow/`, { body: { on: !wall.data.following } });
      wall.setData({ ...wall.data, following: r.following, followers: r.followers });
    } catch (e) {
      fail(e);
    }
  };
  const tabs: { key: Tab; label: string }[] = [...(feedOn ? [{ key: 'wall' as const, label: t('Записи') }] : []), { key: 'pubs', label: t('Публикации') },
    ...(data.thread ? [{ key: 'media' as const, label: t('Медиа') }, { key: 'files' as const, label: t('Файлы') }] : [])];
  const joined = new Date(data.joined).toLocaleDateString(lang === 'en' ? 'en-US' : lang === 'uz' ? 'uz-UZ' : 'ru-RU', { month: 'long', year: 'numeric' });
  const none = (text: string) => <Txt kind="muted" style={{ textAlign: 'center', padding: 26 }}>{text}</Txt>;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top']}>
      <OfflineBar />
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 10, paddingTop: 4 }}>
        <Pressable onPress={back} hitSlop={12} style={{ padding: 4 }}><Icon name="chevron-back" size={27} color={c.accent} /></Pressable>
        {!data.me ? <Pressable onPress={() => setMenu(true)} hitSlop={12} style={{ padding: 6 }} accessibilityLabel={t('Ещё')}><Icon name="ellipsis-vertical" size={21} color={c.ink} /></Pressable> : null}
      </View>
      <ScrollView contentContainerStyle={{ padding: 16, paddingTop: 0, gap: 14, paddingBottom: 48 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={reload} tintColor={c.accent} />}>
        <ProfileHead name={data.name} avatar={data.avatar} hue={data.id} verified={data.verified} photos={data.photos?.length}
          onAvatar={data.photos?.length ? () => setPhoto(0) : undefined}
          status={data.me ? t('в сети') : statusText(data.presence, t, lang)} online={data.me || data.presence.online} />
        {data.blocked_any && !data.me ? <Txt kind="muted" style={{ textAlign: 'center' }}>{data.blocked ? t('Вы заблокировали этого человека.') : t('Переписка недоступна: один из вас заблокировал другого.')}</Txt> : null}
        {wall.data && !wall.data.counts_hidden ? (
          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 18 }}>
            {([[wall.data.posts ?? 0, t('записей')], [wall.data.followers ?? 0, t('подписчиков')], [wall.data.follows ?? 0, t('подписок')]] as const).map(([n, label]) => (
              <Txt key={label} kind="small"><Txt style={{ fontWeight: '800' }}>{n}</Txt> {label}</Txt>
            ))}
          </View>
        ) : null}
        {wall.data && !data.me ? (
          <Press onPress={follow} haptic style={{ alignSelf: 'stretch', alignItems: 'center', paddingVertical: 11, borderRadius: 14, backgroundColor: wall.data.following ? c.card : c.accent }}>
            <Txt style={{ fontWeight: '800' }} color={wall.data.following ? c.ink : '#fff'}>{wall.data.following ? t('Вы подписаны') : t('Подписаться')}</Txt>
          </Press>
        ) : null}
        {actions.length ? <ProfileActions items={actions} /> : null}
        <ProfileInfo phone={data.phone} handle={data.handle} bio={data.bio} city={data.city} links={data.links} joined={joined} mine={data.me} />

        {tabs.length > 1 ? <Segmented value={tabNow} onChange={setTab} options={tabs} /> : <Txt kind="label" style={{ paddingHorizontal: 4 }}>{t('Публикации')}</Txt>}
        {tabNow === 'wall' ? (
          wall.data?.items.length ? (
            <View style={{ marginHorizontal: -16 }}>
              {wall.data.items.map((x) => (
                <FeedCard key={x.key} x={x} onChange={(n) => wall.setData({ ...wall.data!, items: wall.data!.items.map((y) => (y.key === n.key ? n : y)) })}
                  onRemove={(k) => wall.setData({ ...wall.data!, items: wall.data!.items.filter((y) => y.key !== k) })} />
              ))}
            </View>
          ) : wall.loading ? <Loading /> : none(t('Записей пока нет.'))
        ) : null}
        {tabNow === 'pubs' ? (
          data.pubs.length ? (
            <View style={{ backgroundColor: c.card, borderRadius: 20, overflow: 'hidden' }}>
              {data.pubs.map((p, i) => (
                <Press key={`${p.type}${p.id}`} onPress={() => router.push(`/pub/${p.type}/${p.id}`)} scale={0.985}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
                  {p.image ? <Image source={{ uri: p.image }} style={{ width: 52, height: 52, borderRadius: 12, backgroundColor: c.card2 }} contentFit="cover" />
                    : <View style={{ width: 52, height: 52, borderRadius: 12, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}><Icon name="pricetag-outline" size={22} color={c.accent} /></View>}
                  <View style={{ flex: 1 }}>
                    <Txt style={{ fontWeight: '700' }} numberOfLines={1}>{p.title}</Txt>
                    {p.subtitle ? <Txt kind="small" numberOfLines={1}>{p.subtitle}</Txt> : null}
                  </View>
                  <Icon name="chevron-forward" size={17} color={c.inkSoft} />
                </Press>
              ))}
            </View>
          ) : none(t('Публикаций пока нет.'))
        ) : null}
        {tabNow === 'media' ? (
          media.data?.items.length ? (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 3, borderRadius: 16, overflow: 'hidden' }}>
              {media.data.items.map((m) => (
                <Pressable key={m.id} onPress={() => router.push(`/chat/${data.thread}`)} style={{ width: cell, height: cell, backgroundColor: c.card2, alignItems: 'center', justifyContent: 'center' }}>
                  {m.kind === 'photo' ? <Image source={{ uri: chatFileUrl(m.id), headers: authHeaders() }} style={{ width: cell, height: cell }} contentFit="cover" />
                    : <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(15,17,30,0.55)', alignItems: 'center', justifyContent: 'center' }}><Icon name="play" size={20} color="#fff" /></View>}
                </Pressable>
              ))}
            </View>
          ) : media.loading ? <Loading /> : none(t('В вашей переписке пока нет фото и видео.'))
        ) : null}
        {tabNow === 'files' ? (
          files.data?.items.length ? (
            <View style={{ backgroundColor: c.card, borderRadius: 20, paddingHorizontal: 8, paddingVertical: 4 }}>
              {files.data.items.map((m) => <ChatFile key={m.id} uri={chatFileUrl(m.id)} name={m.file_name ?? ''} size={m.file_size ?? 0} mine={false} />)}
            </View>
          ) : files.loading ? <Loading /> : none(t('В вашей переписке пока нет файлов.'))
        ) : null}
      </ScrollView>
      <PhotoViewer photos={(data.photos ?? []).map((p) => ({ ...p, name: data.name }))} index={photo} onClose={() => setPhoto(null)} />
      <Sheet open={menu} onClose={() => setMenu(false)} title={data.name} items={[
        { icon: data.contact ? 'person-remove-outline' : 'person-add-outline', title: data.contact ? t('Удалить из контактов') : t('Добавить в контакты'),
          onPress: async () => {
            try {
              await api('/contacts/', { body: data.contact ? { remove: data.id } : { user: data.id } });
              setData({ ...data, contact: !data.contact });
            } catch (e) {
              fail(e);
            }
          } },
        { icon: data.close ? 'heart-dislike-outline' : 'heart-outline', title: data.close ? t('Убрать из близких друзей') : t('Добавить в близкие друзья'),
          subtitle: t('Близким видно то, что вы скрыли от остальных'), onPress: close },
        { icon: 'flag-outline', title: t('Пожаловаться'), onPress: () => router.push({ pathname: '/report', params: { type: 'user', id: String(data.id), user_id: String(data.id) } }) },
        { icon: 'ban-outline', danger: true, title: data.blocked ? t('Разблокировать') : t('Заблокировать'), onPress: block },
      ]} />
    </SafeAreaView>
  );
}
