import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { FlatList, Pressable, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, cachedGet } from '@/lib/api';
import { shortDate } from '@/lib/hijri';
import { openWeb } from '@/lib/links';
import { ADD_PATH, PUB_TITLES } from '@/lib/modules';
import { useApp } from '@/state/app';
import { Chip, Empty, ErrorBox, Field, Icon, Loading, OfflineBar, Txt } from '@/ui/kit';

type Item = { id: number; title: string; subtitle: string; image: string; created_at: string; verified: boolean };

export default function PubList() {
  const { key } = useLocalSearchParams<{ key: string }>();
  const { c, t, user, langTick } = useApp();
  const [q, setQ] = useState('');
  const [cat, setCat] = useState('');
  const [items, setItems] = useState<Item[]>([]);
  const [cats, setCats] = useState<{ key: string; name: string; emoji?: string }[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async (page = 1) => {
    setLoading(true);
    const qs = `?page=${page}&q=${encodeURIComponent(q)}&category=${encodeURIComponent(cat)}`;
    try {
      const { data } = page === 1 ? await cachedGet(`/pubs/${key}/${qs}`) : { data: await api(`/pubs/${key}/${qs}`) };
      setItems((old) => (page === 1 ? data.items : [...old, ...data.items]));
      if (data.categories?.length) setCats(data.categories);
      setNext(data.next);
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
  }, [key, q, cat, langTick]);

  // форма в приложении; книги (файл книги) — пока на сайте
  const add = () => (!user ? router.push('/login') : key === 'books' ? openWeb(ADD_PATH[key]) : router.push(`/publish/${key}`));

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top']}>
      <OfflineBar />
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 8, gap: 8 }}>
        <Pressable onPress={() => router.back()} hitSlop={12}><Icon name="chevron-back" size={26} color={c.accent} /></Pressable>
        <Txt kind="h2" style={{ flex: 1 }} numberOfLines={1}>{t(PUB_TITLES[key] ?? '')}</Txt>
        {ADD_PATH[key] ? (
          <Pressable onPress={add} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: c.accent, borderRadius: 999, paddingVertical: 7, paddingHorizontal: 12 }}>
            <Icon name="add" size={18} color="#fff" /><Txt kind="small" color="#fff" style={{ fontWeight: '700' }}>{t('Добавить')}</Txt>
          </Pressable>
        ) : null}
      </View>
      <View style={{ paddingHorizontal: 16, gap: 10, paddingBottom: 6 }}>
        <Field placeholder={t('Поиск')} value={q} onChangeText={setQ} returnKeyType="search" />
        {cats.length ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
            <Chip label={t('Все')} on={!cat} onPress={() => setCat('')} />
            {cats.map((x) => <Chip key={x.key} label={`${x.emoji ? x.emoji + ' ' : ''}${x.name}`} on={cat === x.key} onPress={() => setCat(x.key)} />)}
          </ScrollView>
        ) : null}
      </View>
      <FlatList
        data={items}
        keyExtractor={(x) => String(x.id)}
        contentContainerStyle={{ padding: 16, gap: 10, paddingBottom: 40 }}
        onEndReached={() => next && !loading && load(next)}
        onEndReachedThreshold={0.4}
        refreshing={loading && items.length > 0}
        onRefresh={() => load(1)}
        ListEmptyComponent={loading ? <Loading /> : error ? <ErrorBox error={error} onRetry={() => load(1)} /> : <Empty title={t('Пока ничего нет')} text={q ? t('Попробуйте другой запрос') : undefined} />}
        renderItem={({ item }) => (
          <Pressable onPress={() => router.push(`/pub/${key}/${item.id}`)} style={({ pressed }) => ({
            flexDirection: 'row', gap: 12, backgroundColor: c.card, borderRadius: 20, padding: 12, opacity: pressed ? 0.8 : 1 })}>
            {item.image ? <Image source={{ uri: item.image }} style={{ width: 84, height: 84, borderRadius: 14, backgroundColor: c.card2 }} contentFit="cover" transition={150} />
              : null}
            <View style={{ flex: 1, gap: 4, justifyContent: 'center' }}>
              <Txt kind="h3" numberOfLines={2}>{item.title}{item.verified ? ' ✓' : ''}</Txt>
              {item.subtitle ? <Txt kind="small" numberOfLines={2} color={c.accentD} style={{ fontWeight: '600' }}>{item.subtitle}</Txt> : null}
              <Txt kind="small">{shortDate(item.created_at)}</Txt>
            </View>
          </Pressable>
        )}
      />
    </SafeAreaView>
  );
}
