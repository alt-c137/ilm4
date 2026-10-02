import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, FlatList, Pressable, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Chip, Empty, ErrorBox, Field, Icon, OfflineBar, Press, Skeleton, Txt } from '@/ui/kit';

type Room = { id: number; kind: 'group' | 'channel'; title: string; about: string; handle: string; avatar: string; members: number;
  verified: boolean; member: boolean };

/** Каталог публичных каналов и групп. Сюда же ведут ссылки ilm4.com/c/имя и ссылки-приглашения. */
export default function Channels() {
  const { handle, code } = useLocalSearchParams<{ handle?: string; code?: string }>();
  const { c, t } = useApp();
  const [q, setQ] = useState('');
  const [kind, setKind] = useState('');
  const [items, setItems] = useState<Room[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async (page = 1) => {
    setLoading(true);
    try {
      const r = await api(`/chat/rooms/?page=${page}&q=${encodeURIComponent(q)}&kind=${kind}`);
      setItems((old) => (page === 1 ? r.items : [...old, ...r.items]));
      setNext(r.next);
      setError('');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    const id = setTimeout(() => load(1), q ? 350 : 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, kind]);

  // пришли по ссылке: публичное имя — открыть канал, приглашение — спросить и вступить
  useEffect(() => {
    if (handle) {
      api<Room>(`/chat/c/${handle}/`).then((r) => router.replace(`/chat/${r.id}`)).catch((e) => Alert.alert(e.message));
    } else if (code) {
      api<Room>(`/chat/join/${code}/`).then((r) => {
        if (r.member) return router.replace(`/chat/${r.id}`);
        Alert.alert(r.title, r.about || undefined, [
          { text: t('Отмена'), style: 'cancel' },
          { text: r.kind === 'channel' ? t('Подписаться') : t('Вступить в группу'), onPress: async () => {
            try {
              await api(`/chat/join/${code}/`, { body: {} });
              router.replace(`/chat/${r.id}`);
            } catch (e: any) {
              Alert.alert(e.message);
            }
          } },
        ]);
      }).catch((e) => Alert.alert(e.message));
    }
  }, [handle, code, t]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top']}>
      <OfflineBar />
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 8, gap: 8 }}>
        <Pressable onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} hitSlop={12}><Icon name="chevron-back" size={26} color={c.accent} /></Pressable>
        <Txt kind="h2" style={{ flex: 1 }} numberOfLines={1}>{t('Каналы и группы')}</Txt>
        <Pressable onPress={() => router.push({ pathname: '/chat/new', params: { kind: 'channel' } })}
          style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: c.accent, borderRadius: 999, paddingVertical: 7, paddingHorizontal: 12 }}>
          <Icon name="add" size={18} color="#fff" /><Txt kind="small" color="#fff" style={{ fontWeight: '700' }}>{t('Создать')}</Txt>
        </Pressable>
      </View>
      <View style={{ paddingHorizontal: 16, gap: 10, paddingBottom: 6 }}>
        <Field placeholder={t('Название, тема или @имя')} value={q} onChangeText={setQ} returnKeyType="search" autoCapitalize="none" />
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Chip label={t('Все')} on={!kind} onPress={() => setKind('')} />
          <Chip label={t('Каналы')} on={kind === 'channel'} onPress={() => setKind('channel')} />
          <Chip label={t('Группы')} on={kind === 'group'} onPress={() => setKind('group')} />
        </View>
      </View>
      <FlatList
        data={items}
        keyExtractor={(x) => String(x.id)}
        contentContainerStyle={{ padding: 16, gap: 10, paddingBottom: 40 }}
        onEndReached={() => next && !loading && load(next)}
        onEndReachedThreshold={0.4}
        refreshing={loading && items.length > 0}
        onRefresh={() => load(1)}
        ListEmptyComponent={loading ? <Skeleton image /> : error ? <ErrorBox error={error} onRetry={() => load(1)} />
          : <Empty icon="megaphone-outline" title={q ? t('Ничего не нашлось') : t('Публичных каналов пока нет')} text={t('Заведите канал своей мечети, уроков или общины — его увидят все.')} />}
        renderItem={({ item }) => (
          <Press onPress={() => router.push(`/chat/${item.id}`)} scale={0.98}
            style={{ flexDirection: 'row', gap: 12, alignItems: 'center', backgroundColor: c.card, borderRadius: 20, padding: 12 }}>
            <Avatar uri={item.avatar} name={item.title} size={56} hue={item.id} />
            <View style={{ flex: 1, gap: 2 }}>
              <Txt kind="h3" numberOfLines={1}>{item.title}{item.verified ? ' ✓' : ''}</Txt>
              <Txt kind="small" numberOfLines={1}>
                {item.kind === 'channel' ? t('канал · подписчиков: {n}', { n: item.members }) : t('группа · участников: {n}', { n: item.members })}
                {item.handle ? ` · @${item.handle}` : ''}</Txt>
              {item.about ? <Txt kind="small" numberOfLines={2} color={c.ink}>{item.about}</Txt> : null}
            </View>
            {item.member ? <Icon name="checkmark-circle" size={22} color={c.accent} /> : <Icon name="chevron-forward" size={18} color={c.inkSoft} />}
          </Press>
        )}
      />
    </SafeAreaView>
  );
}
