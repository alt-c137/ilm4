import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, View } from 'react-native';

import { api } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, ErrorBox, Icon, Loading, Screen, Section, Txt } from '@/ui/kit';
import { KV, ProfileHead, type NkProfile } from '@/ui/nikah';
import { useFetch } from '@/ui/useFetch';

type Full = NkProfile & { liked: boolean; likes_me: boolean; saved: boolean; match_id: number | null; user_id: number };

export default function NikahProfile() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { c, t } = useApp();
  const { data: p, setData, loading, error, reload } = useFetch<Full>(`/nikah/p/${id}/`);
  const [busy, setBusy] = useState(false);
  if (!p) return <Screen back title="">{loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />}</Screen>;
  const brother = p.gender === 'M';

  const like = async (undo = false) => {
    setBusy(true);
    try {
      const r = await api(`/nikah/p/${p.id}/interest/`, { body: undo ? { undo: 1 } : {} });
      setData({ ...p, liked: !undo, match_id: r.match_id ?? p.match_id });
      if (r.match_id) router.push(`/nikah/match/${r.match_id}`);
      else if (!undo) Alert.alert(t('Интерес отправлен. Если он взаимный — вы оба узнаете.'));
    } catch (e: any) {
      Alert.alert(e.message);
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    const r = await api(`/nikah/p/${p.id}/save/`, { body: {} }).catch(() => null);
    if (r) setData({ ...p, saved: r.saved });
  };

  return (
    <Screen back title={t('Анкета')} right={
      <View style={{ flexDirection: 'row', gap: 16 }}>
        <Pressable onPress={save} hitSlop={8}><Icon name={p.saved ? 'star' : 'star-outline'} color={c.accent} /></Pressable>
        <Pressable onPress={() => router.push({ pathname: '/report', params: { type: 'nikah', id: String(p.id), user_id: String(p.user_id) } })} hitSlop={8}>
          <Icon name="flag-outline" color={c.inkSoft} /></Pressable>
      </View>}>
      <Card style={{ gap: 12 }}>
        <ProfileHead p={p} />
        {p.why?.length ? <Txt kind="small" color={c.accentD}>✓ {p.why.join(' · ')}</Txt> : null}
      </Card>
      {p.match_id ? (
        <Card onPress={() => router.push(`/nikah/match/${p.match_id}`)} style={{ flexDirection: 'row', gap: 12, alignItems: 'center', backgroundColor: c.accentSoft }}>
          <Icon name="heart" color="#e0457b" /><Txt kind="h3" style={{ flex: 1 }}>{t('Взаимная симпатия — открыть')}</Txt><Icon name="chevron-forward" color={c.accent} />
        </Card>
      ) : p.likes_me ? (
        <Card soft><Txt kind="h3">{brother ? t('Брат проявил интерес к вам') : t('Сестра проявила интерес к вам')}</Txt>
          <Txt kind="small">{t('Ответьте взаимностью — откроется следующий шаг.')}</Txt></Card>
      ) : null}
      <Section title={t('Вероубеждение и манхадж')}>
        <KV items={[[t('Вероубеждение'), p.aqida], [t('Мазхаб'), p.madhhab], [t('Намаз'), p.prayer], [t('Коран'), p.quran],
          [t('Где Аллах?'), p.where_allah], [brother ? t('Борода') : t('Покрытие'), p.look]]} />
        {p.manhaj_text ? <Card><Txt selectable>{p.manhaj_text}</Txt></Card> : null}
      </Section>
      <Section title={t('О себе')}><Card><Txt selectable>{p.about}</Txt></Card></Section>
      <Section title={brother ? t('Какую жену ищет') : t('Какого мужа ищет')}>
        <Card style={{ gap: 6 }}>
          <Txt selectable>{p.partner_expectations}</Txt>
          <Txt kind="small">{t('Возраст')}: {p.age_from}–{p.age_to}</Txt>
        </Card>
      </Section>
      <Section title={t('Семья и планы')}>
        <KV items={[[t('Семейное положение'), p.marital], [brother ? t('Ищет жену') : t('Многожёнство'), brother ? p.wife_number : p.polygyny],
          [t('Свои дети'), p.children_want], [t('Дети партнёра'), p.children_accept], [t('Готовность к никяху'), p.ready_when],
          [t('Переезд'), p.relocation], [t('Рост'), p.height ? `${p.height} ${t('см')}` : ''], [t('Вес'), p.weight ? `${p.weight} ${t('кг')}` : '']]} />
      </Section>
      {!p.match_id ? (p.liked
        ? <Button kind="soft" title={t('Интерес отправлен · отозвать')} icon="heart" onPress={() => like(true)} loading={busy} />
        : <Button title={p.likes_me ? t('Ответить взаимностью') : t('Проявить интерес')} icon="heart" onPress={() => like()} loading={busy} />) : null}
    </Screen>
  );
}
