import { Image } from 'expo-image';
import { useLocalSearchParams } from 'expo-router';
import { Pressable, Share } from 'react-native';

import { shortDate } from '@/lib/hijri';
import { useApp } from '@/state/app';
import { ErrorBox, Icon, Loading, Screen, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

export default function NewsPost() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { c, t } = useApp();
  const { data, loading, error, reload } = useFetch<any>(`/news/${id}/`);
  return (
    <Screen back title={t('Новости')} right={data?.url ? (
      <Pressable onPress={() => Share.share({ message: `${data.title}\n${data.url}` })}><Icon name="share-outline" color={c.accent} /></Pressable>) : null}>
      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : (
        <>
          {data.image ? <Image source={{ uri: data.image }} style={{ width: '100%', aspectRatio: 16 / 9, borderRadius: 20 }} contentFit="cover" /> : null}
          <Txt kind="h1" selectable>{data.title}</Txt>
          <Txt kind="small">{shortDate(data.created_at)}</Txt>
          {data.summary ? <Txt kind="h3" style={{ fontWeight: '600' }}>{data.summary}</Txt> : null}
          <Txt selectable style={{ fontSize: 16, lineHeight: 25 }}>{data.text}</Txt>
        </>
      )}
    </Screen>
  );
}
