import { Image } from 'expo-image';
import { router } from 'expo-router';
import { View } from 'react-native';

import { shortDate } from '@/lib/hijri';
import { useApp } from '@/state/app';
import { Card, Empty, ErrorBox, Icon, Loading, Screen, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

export default function News() {
  const { c, t } = useApp();
  const { data, loading, error, reload } = useFetch<{ items: any[] }>('/news/');
  return (
    <Screen title={t('Новости')} back onRefresh={reload} refreshing={loading && !!data}>
      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : !data.items.length ? <Empty title={t('Пока нет новостей')} /> : null}
      {data?.items.map((n) => (
        <Card key={n.id} onPress={() => router.push(`/news/${n.id}`)} style={{ padding: 0, overflow: 'hidden' }}>
          {n.image ? <Image source={{ uri: n.image }} style={{ width: '100%', aspectRatio: 16 / 9 }} contentFit="cover" /> : null}
          <View style={{ padding: 14, gap: 6 }}>
            <Txt kind="h3">{n.pinned ? <Icon name="pin" size={16} color={c.accent} /> : null}{n.pinned ? ' ' : ''}{n.title}</Txt>
            {n.summary ? <Txt kind="muted" numberOfLines={3}>{n.summary}</Txt> : null}
            <Txt kind="small">{shortDate(n.created_at)}</Txt>
          </View>
        </Card>
      ))}
    </Screen>
  );
}
