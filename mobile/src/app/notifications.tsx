import { useEffect } from 'react';
import { View } from 'react-native';

import { api } from '@/lib/api';
import { shortDate } from '@/lib/hijri';
import { openSiteUrl } from '@/lib/links';
import { useApp } from '@/state/app';
import { Card, Empty, ErrorBox, Loading, Screen, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

export default function Notifications() {
  const { c, t } = useApp();
  const { data, loading, error, reload } = useFetch<{ items: { id: number; text: string; url: string; read: boolean; created_at: string }[] }>('/notifications/');
  useEffect(() => {
    if (data?.items.some((n) => !n.read)) api('/notifications/read/', { body: {} }).catch(() => {});
  }, [data]);
  return (
    <Screen title={t('Уведомления')} back onRefresh={reload} refreshing={loading && !!data}>
      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : !data.items.length ? (
        <Empty icon="notifications-outline" title={t('Уведомлений пока нет')} />
      ) : data.items.map((n) => (
        <Card key={n.id} onPress={n.url ? () => openSiteUrl(n.url) : undefined} style={{ flexDirection: 'row', gap: 10 }}>
          {!n.read ? <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: c.accent, marginTop: 7 }} /> : null}
          <View style={{ flex: 1, gap: 4 }}>
            <Txt>{n.text}</Txt>
            <Txt kind="small">{shortDate(n.created_at)}</Txt>
          </View>
        </Card>
      ))}
    </Screen>
  );
}
