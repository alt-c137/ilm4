import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Pressable, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, Empty, ErrorBox, Icon, Loading, Press, Screen, Section, Txt } from '@/ui/kit';
import { HabitRow, isoDay, Ring, type Habit } from '@/ui/tracker';
import { useFetch } from '@/ui/useFetch';

type Day = { day: string; n: number; done: number; total: number; today: boolean; future: boolean };
type Board = { id: number; title: string; emoji: string; compete: boolean; members: number; owner: boolean };
type Data = { day: string; today: string; items: Habit[]; done: number; total: number; week: Day[]; habits_total: number; boards: Board[] };
const WD = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

function shift(iso: string, days: number) {
  const [y, m, d] = iso.split('-').map(Number);
  return isoDay(new Date(y, m - 1, d + days));
}

/** Трекер привычек: что нужно сегодня, отметки, неделя, общие трекеры. Можно поставить нижней кнопкой. */
export default function Tracker() {
  const { c, t, user, tabs } = useApp();
  const [day, setDay] = useState(isoDay());
  const { data, setData, loading, error, reload } = useFetch<Data>(user ? `/tracker/?day=${day}` : null);
  useFocusEffect(useCallback(() => { if (user) reload(true); }, [user, reload]));
  const asTab = tabs.includes('tracker');

  if (!user) {
    return (
      <Screen title={t('Трекер')} back={!asTab}>
        <Empty icon="checkmark-circle-outline" title={t('Войдите, чтобы вести трекер')} text={t('Привычки и дела на день — одному или вместе с близкими.')}
          action={<Button title={t('Войти')} onPress={() => router.push('/login')} />} />
      </Screen>
    );
  }

  const mark = async (h: Habit, value?: number) => {
    if (!data) return;
    // сразу показываем результат, сервер подтвердит
    const guess = value ?? (h.done ? 0 : h.kind === 'check' ? h.target : h.value + 1);
    const paint = (v: number) => setData({ ...data, items: data.items.map((x) => (x.id === h.id ? { ...x, value: v, done: v >= x.target } : x)) });
    paint(guess);
    try {
      const r = await api<{ value: number }>(`/tracker/habits/${h.id}/log/`, { body: value === undefined ? { day } : { day, value } });
      paint(r.value);
      reload(true);
    } catch (e) {
      paint(h.value);
      Alert.alert((e as ApiError).message);
    }
  };
  const edit = (h: Habit) => router.push({ pathname: '/habits/edit', params: { id: String(h.id) } });
  const items = data?.items ?? [];
  const done = items.filter((x) => x.done).length;
  const percent = items.length ? Math.round((100 * done) / items.length) : 0;
  const today = data?.today ?? isoDay();
  const canMark = day <= today && day >= shift(today, -7);
  const [, mm, dd] = day.split('-').map(Number);

  return (
    <Screen title={t('Трекер')} back={!asTab} onRefresh={reload} refreshing={loading && !!data}
      right={
        <View style={{ flexDirection: 'row', gap: 16, alignItems: 'center' }}>
          <Pressable onPress={() => router.push('/habits/stats')} hitSlop={8} accessibilityLabel={t('Графики')}><Icon name="bar-chart-outline" size={23} color={c.accent} /></Pressable>
          <Pressable onPress={() => router.push('/habits/edit')} hitSlop={8} accessibilityLabel={t('Добавить')}><Icon name="add-circle" size={28} color={c.accent} /></Pressable>
        </View>}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
        <Pressable onPress={() => setDay(shift(day, -7))} hitSlop={8}><Icon name="chevron-back" size={20} color={c.inkSoft} /></Pressable>
        {(data?.week ?? []).map((d, i) => {
          const on = d.day === day;
          const full = d.total > 0 && d.done === d.total;
          return (
            <Pressable key={d.day} onPress={() => setDay(d.day)} style={{ flex: 1, alignItems: 'center', paddingVertical: 7, borderRadius: 14, backgroundColor: on ? c.accent : c.card }}>
              <Txt kind="small" style={{ fontSize: 11, fontWeight: '600' }} color={on ? '#fff' : c.inkSoft}>{t(WD[i])}</Txt>
              <Txt style={{ fontSize: 16, fontWeight: '800' }} color={on ? '#fff' : d.today ? c.accent : c.ink}>{d.n}</Txt>
              <Txt style={{ fontSize: 10, lineHeight: 13, fontWeight: full ? '800' : '400' }} color={on ? '#fff' : full ? c.ok : c.inkSoft}>{d.total ? `${d.done}/${d.total}` : '·'}</Txt>
            </Pressable>
          );
        })}
        <Pressable onPress={() => setDay(shift(day, 7))} hitSlop={8}><Icon name="chevron-forward" size={20} color={c.inkSoft} /></Pressable>
      </View>

      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : items.length ? (
        <>
          <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 16 }}>
            <Ring percent={percent} />
            <View style={{ flex: 1 }}>
              <Txt style={{ fontSize: 21, fontWeight: '800' }}>{done} / {items.length}</Txt>
              <Txt kind="small">{percent === 100 ? t('Всё сделано, ма шаа Аллах!') : day === today ? t('выполнено сегодня') : `${t('выполнено')} · ${String(dd).padStart(2, '0')}.${String(mm).padStart(2, '0')}`}</Txt>
            </View>
          </Card>
          <View style={{ gap: 8 }}>
            {items.map((h) => <HabitRow key={h.id} h={h} canMark={canMark} onToggle={(x) => mark(x)} onStep={(x, by) => mark(x, Math.max(0, x.value + by))} onEdit={edit} />)}
          </View>
        </>
      ) : (
        <Empty icon="checkmark-circle-outline" title={data.habits_total ? t('На этот день ничего не запланировано') : t('Начните с одной привычки')}
          text={t('Таблетки, вода, чтение, зарядка, слова на арабском — что угодно. Отмечайте каждый день и смотрите, как растёт серия.')}
          action={<Button small title={t('Добавить привычку')} icon="add" onPress={() => router.push('/habits/edit')} />} />
      )}
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Button small kind="soft" icon="add" title={t('Привычка')} style={{ flex: 1 }} onPress={() => router.push('/habits/edit')} />
        <Button small kind="soft" icon="add" title={t('Дело на день')} style={{ flex: 1 }} onPress={() => router.push({ pathname: '/habits/edit', params: { once: day } })} />
      </View>

      <Section title={t('Вместе')}>
        {(data?.boards ?? []).map((b) => (
          <Press key={b.id} onPress={() => router.push(`/habits/board/${b.id}`)} scale={0.985}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: c.card, borderRadius: 18, padding: 14 }}>
            <Txt style={{ fontSize: 26, lineHeight: 31 }}>{b.emoji}</Txt>
            <View style={{ flex: 1 }}>
              <Txt style={{ fontWeight: '700', fontSize: 15.5 }} numberOfLines={1}>{b.title}</Txt>
              <Txt kind="small">{t('участников: {n}', { n: b.members })}{b.compete ? ' · 🏆' : ''}</Txt>
            </View>
            <Icon name="chevron-forward" size={18} color={c.inkSoft} />
          </Press>
        ))}
        <Press onPress={() => router.push('/habits/board-new')} scale={0.985}
          style={{ flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 18, padding: 14, borderWidth: 1.5, borderStyle: 'dashed', borderColor: c.line }}>
          <Icon name="add" size={26} color={c.accent} />
          <View style={{ flex: 1 }}>
            <Txt style={{ fontWeight: '700', fontSize: 15.5 }}>{t('Общий трекер')}</Txt>
            <Txt kind="small">{t('с семьёй, друзьями, напарниками')}</Txt>
          </View>
        </Press>
        <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 4 }}>
          <Icon name="lock-closed-outline" size={14} color={c.inkSoft} />
          <Txt kind="small" style={{ flex: 1, fontSize: 12.5 }}>{t('Свои привычки видите только вы. В общем трекере участники видят отметки друг друга.')}</Txt>
        </View>
      </Section>
    </Screen>
  );
}
