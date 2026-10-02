import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { View } from 'react-native';

import { useApp } from '@/state/app';
import { Badge, Card, Empty, ErrorBox, Icon, Loading, Screen, Segmented, Txt } from '@/ui/kit';
import { Compat, type NkProfile } from '@/ui/nikah';
import { useFetch } from '@/ui/useFetch';

type Match = { id: number; stage: string; stage_name: string; my_turn: boolean; thread_id: number | null; partner: NkProfile };
type Lists = { incoming: NkProfile[]; sent: NkProfile[]; saved: NkProfile[]; matches: Match[] };

export default function NikahLists() {
  const { c, t } = useApp();
  const [tab, setTab] = useState<'incoming' | 'matches' | 'sent' | 'saved'>('incoming');
  const { data, loading, error, reload } = useFetch<Lists>('/nikah/lists/');
  useFocusEffect(useCallback(() => { reload(true); }, [reload]));

  const row = (p: NkProfile, onPress: () => void, extra?: React.ReactNode) => (
    <Card key={`${tab}-${p.id}`} onPress={onPress} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
      <View style={{ flex: 1, gap: 2 }}>
        <Txt kind="h3">{p.name}, {p.age}{p.verified ? ' ✓' : ''}</Txt>
        <Txt kind="small" numberOfLines={1}>{p.place}</Txt>
        {extra}
      </View>
      {p.compat !== undefined ? <Compat value={p.compat} size={46} /> : null}
    </Card>
  );

  return (
    <Screen back title={t('Симпатии')} onRefresh={reload} refreshing={loading && !!data}>
      <Segmented value={tab} onChange={setTab} options={[
        { key: 'incoming', label: `${t('Ко мне')}${data?.incoming.length ? ` · ${data.incoming.length}` : ''}` },
        { key: 'matches', label: t('Пары') }, { key: 'sent', label: t('Мои') }, { key: 'saved', label: t('★') },
      ]} />
      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : (
        <>
          {tab === 'incoming' && (data.incoming.length ? data.incoming.map((p) => row(p, () => router.push(`/nikah/${p.id}`)))
            : <Empty icon="heart-outline" title={t('Пока никто не проявил интерес')} text={t('Заполненная анкета и верификация помогают.')} />)}
          {tab === 'sent' && (data.sent.length ? data.sent.map((p) => row(p, () => router.push(`/nikah/${p.id}`)))
            : <Empty icon="paper-plane-outline" title={t('Вы ещё никому не отправили интерес')} />)}
          {tab === 'saved' && (data.saved.length ? data.saved.map((p) => row(p, () => router.push(`/nikah/${p.id}`)))
            : <Empty icon="star-outline" title={t('Сохранённых анкет нет')} />)}
          {tab === 'matches' && (data.matches.length ? data.matches.map((m) => row(m.partner, () => router.push(`/nikah/match/${m.id}`), (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Icon name={m.stage === 'chat' ? 'chatbubbles' : m.stage === 'closed' ? 'close-circle' : 'images'} size={14}
                color={m.stage === 'closed' ? c.inkSoft : c.accent} />
              <Txt kind="small" color={m.my_turn ? c.accentD : undefined} style={{ fontWeight: m.my_turn ? '700' : '400' }}>
                {m.my_turn ? t('Ваша очередь') : m.stage_name}
              </Txt>
              {m.my_turn ? <Badge n={1} /> : null}
            </View>
          ))) : <Empty icon="heart-half-outline" title={t('Взаимных симпатий пока нет')} />)}
        </>
      )}
    </Screen>
  );
}
