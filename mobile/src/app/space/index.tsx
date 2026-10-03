import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, TextInput, View } from 'react-native';

import { useApp } from '@/state/app';
import { Avatar, Button, Card, Empty, ErrorBox, Icon, Loading, Screen, Section, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

export type SpaceCard = { id: number; title: string; about: string; icon: string; members: number; public: boolean; verified: boolean; member: boolean };

/** Сообщества — как серверы в Discord: мои и каталог открытых. Внутри — каналы-чаты, роли, свой ник. */
export default function Spaces() {
  const { c, t, user } = useApp();
  const [q, setQ] = useState('');
  const { data, loading, error, reload } = useFetch<{ mine: SpaceCard[]; catalog: SpaceCard[] }>(user ? `/communities/?q=${encodeURIComponent(q.trim())}` : null, [q]);
  useFocusEffect(useCallback(() => { reload(true); }, [reload]));

  if (!user) {
    return (
      <Screen title={t('Сообщества')} back>
        <Empty icon="people-outline" title={t('Сообщества')} text={t('Клубы по интересам: в каждом — свои каналы для разговоров и объявлений, роли и свой ник.')}
          action={<Button title={t('Войти')} onPress={() => router.push('/login')} />} />
      </Screen>
    );
  }
  const row = (s: SpaceCard, i: number) => (
    <Pressable key={s.id} onPress={() => router.push(`/space/${s.id}`)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
      <Avatar uri={s.icon} name={s.title} size={46} hue={s.id} />
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
          <Txt style={{ fontWeight: '700', flexShrink: 1 }} numberOfLines={1}>{s.title}</Txt>
          {s.verified ? <Icon name="checkmark-circle" size={15} color={c.accent} /> : null}
        </View>
        <Txt kind="small" numberOfLines={1}>{[s.about, t('участников: {n}', { n: s.members })].filter(Boolean).join(' · ')}</Txt>
      </View>
      {s.member ? <Icon name="chevron-forward" size={18} color={c.inkSoft} /> : <Txt kind="small" color={c.accentD} style={{ fontWeight: '700' }}>{t('Открыть')}</Txt>}
    </Pressable>
  );
  return (
    <Screen title={t('Сообщества')} back onRefresh={reload} refreshing={loading && !!data}
      right={<Pressable onPress={() => router.push('/space/new')} hitSlop={10} accessibilityLabel={t('Создать')}><Icon name="add-circle" size={28} color={c.accent} /></Pressable>}>
      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : (
        <>
          {data.mine.length ? <Section title={t('Мои сообщества')}><Card style={{ paddingVertical: 4 }}>{data.mine.map(row)}</Card></Section> : null}
          <Section title={t('Каталог')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: c.card, borderRadius: 14, paddingHorizontal: 12, height: 44 }}>
              <Icon name="search" size={18} color={c.inkSoft} />
              <TextInput value={q} onChangeText={setQ} placeholder={t('Найти сообщество')} placeholderTextColor={c.inkSoft} style={{ flex: 1, fontSize: 16, color: c.ink }} autoCorrect={false} />
            </View>
            {data.catalog.length ? <Card style={{ paddingVertical: 4 }}>{data.catalog.map(row)}</Card> : (
              <Empty icon="people-outline" title={q ? t('Ничего не найдено') : t('Открытых сообществ пока нет')}
                text={t('Создайте первое — для своей мечети, города, профессии или увлечения.')} />
            )}
          </Section>
        </>
      )}
    </Screen>
  );
}
