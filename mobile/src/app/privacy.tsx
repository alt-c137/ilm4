import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Switch, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp, type Privacy, type User } from '@/state/app';
import { Avatar, Card, Divider, Press, Row, Screen, Section, Sheet, Txt } from '@/ui/kit';
import { privacyName } from '@/ui/profile';
import { useFetch } from '@/ui/useFetch';

type Person = { id: number; name: string; handle: string; avatar: string };

/** Приватность — как в Telegram: кто видит номер, кто находит по номеру, кто видит время в сети, близкие друзья. */
export default function PrivacyScreen() {
  const { c, t, user, setUser } = useApp();
  const friends = useFetch<{ items: Person[] }>(user ? '/me/close/' : null);
  const [pick, setPick] = useState<'phone_privacy' | 'seen_privacy' | null>(null);
  const reloadFriends = friends.reload;
  useFocusEffect(useCallback(() => { reloadFriends(true); }, [reloadFriends]));
  if (!user) return null;
  const pr = user.privacy ?? { phone: 'nobody' as Privacy, seen: 'all' as Privacy, find_by_phone: true };

  const patch = async (body: Record<string, unknown>) => {
    try {
      setUser({ ...(await api<User>('/me/', { method: 'PATCH', body })), links: user.links });
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const current = pick === 'phone_privacy' ? pr.phone : pr.seen;

  return (
    <Screen title={t('Приватность')} back>
      <Section title={t('Номер телефона')}>
        <Card style={{ paddingVertical: 4 }}>
          <Row icon="call-outline" title={t('Кто видит мой номер')} subtitle={privacyName(pr.phone, t)} onPress={() => setPick('phone_privacy')} />
          <Divider />
          <Row icon="search-outline" title={t('Меня можно найти по номеру')} subtitle={t('Сам номер при этом не показывается')}
            right={<Switch value={pr.find_by_phone} onValueChange={(v) => patch({ find_by_phone: v })} trackColor={{ true: c.accent, false: c.line }} />} />
        </Card>
        {!user.phone_verified ? (
          <Press onPress={() => router.push({ pathname: '/verify-phone', params: { why: 'publish' } })}>
            <Txt kind="small" color={c.accent} style={{ fontWeight: '700', paddingHorizontal: 4 }}>{t('Номер не подтверждён — найти вас по нему пока нельзя. Подтвердить →')}</Txt>
          </Press>
        ) : null}
      </Section>

      <Section title={t('Время в сети')}>
        <Card style={{ paddingVertical: 4 }}>
          <Row icon="time-outline" title={t('Кто видит, когда я в сети')} subtitle={privacyName(pr.seen, t)} onPress={() => setPick('seen_privacy')} />
        </Card>
        <Txt kind="small" style={{ paddingHorizontal: 4 }}>{t('Если скрыть своё время, вы тоже не увидите, когда в сети были другие — вместо этого «был(а) недавно».')}</Txt>
      </Section>

      <Section title={t('Близкие друзья')}>
        <Txt kind="small" style={{ paddingHorizontal: 4 }}>{t('Им видно то, что вы показываете «близким друзьям»: номер, соцсети, время в сети. Добавить человека — в его профиле, меню «⋮».')}</Txt>
        {friends.data?.items.length ? (
          <Card style={{ paddingVertical: 4 }}>
            {friends.data.items.map((p, i) => (
              <View key={p.id}>
                {i ? <Divider /> : null}
                <Press onPress={() => router.push(`/user/${p.id}`)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 9 }}>
                  <Avatar uri={p.avatar} name={p.name} size={40} hue={p.id} />
                  <View style={{ flex: 1 }}>
                    <Txt style={{ fontWeight: '700' }} numberOfLines={1}>{p.name}</Txt>
                    {p.handle ? <Txt kind="small">@{p.handle}</Txt> : null}
                  </View>
                </Press>
              </View>
            ))}
          </Card>
        ) : <Txt kind="muted" style={{ paddingHorizontal: 4 }}>{t('Пока никого.')}</Txt>}
      </Section>

      <Section title={t('Соцсети')}>
        <Card style={{ paddingVertical: 4 }}>
          <Row icon="link-outline" title={t('Соцсети и ссылки')} subtitle={t('Кто видит каждую ссылку — в правке профиля')} onPress={() => router.push('/profile-edit')} />
        </Card>
      </Section>

      <Sheet open={!!pick} onClose={() => setPick(null)} title={pick === 'phone_privacy' ? t('Кто видит мой номер') : t('Кто видит, когда я в сети')}
        items={(['all', 'close', 'nobody'] as Privacy[]).map((p) => ({ title: privacyName(p, t), on: current === p, onPress: () => pick && patch({ [pick]: p }) }))} />
    </Screen>
  );
}
