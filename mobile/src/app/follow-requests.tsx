import { router } from 'expo-router';
import { Alert, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Button, Card, Divider, Empty, Loading, Press, Screen, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type Person = { id: number; name: string; handle: string; avatar: string };

/** Заявки в подписчики закрытого профиля: одобрить или отклонить. */
export default function FollowRequests() {
  const { t, user } = useApp();
  const { data, setData, loading } = useFetch<{ items: Person[] }>(user ? '/feed/requests/' : null);
  const answer = async (id: number, ok: boolean) => {
    try {
      setData(await api<{ items: Person[] }>('/feed/requests/', { body: { user: id, ok } }));
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  return (
    <Screen title={t('Заявки в подписчики')} back>
      {!user?.privacy?.private ? <Txt kind="muted">{t('Профиль открыт: подписаться может любой, заявок не бывает.')}</Txt> : null}
      {!data ? (loading ? <Loading /> : null) : data.items.length ? (
        <Card style={{ paddingVertical: 4 }}>
          {data.items.map((p, i) => (
            <View key={p.id}>
              {i ? <Divider /> : null}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9 }}>
                <Press onPress={() => router.push(`/user/${p.id}`)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 }}>
                  <Avatar uri={p.avatar} name={p.name} size={42} hue={p.id} />
                  <View style={{ flex: 1 }}>
                    <Txt style={{ fontWeight: '700' }} numberOfLines={1}>{p.name}</Txt>
                    {p.handle ? <Txt kind="small">@{p.handle}</Txt> : null}
                  </View>
                </Press>
                <Button small title={t('Одобрить')} onPress={() => answer(p.id, true)} />
                <Button small kind="soft" title={t('Отклонить')} onPress={() => answer(p.id, false)} />
              </View>
            </View>
          ))}
        </Card>
      ) : <Empty icon="person-add-outline" title={t('Заявок нет')} />}
    </Screen>
  );
}
