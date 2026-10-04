import { router, useLocalSearchParams } from 'expo-router';
import { useRef } from 'react';
import { ScrollView, View } from 'react-native';

import { useApp } from '@/state/app';
import { Button, Card, Icon, Loading, Screen, Section, Txt } from '@/ui/kit';
import type { Habit } from '@/ui/tracker';
import { useFetch } from '@/ui/useFetch';

type Cell = { day: string; due: boolean; value: number; skipped: boolean; level: number; note: string };
type Detail = { habit: Habit; cells: Cell[]; streak: number; best: number; done_days: number; total: number;
  months: { month: string; done: number; due: number }[]; notes: { day: string; note: string }[] };

/** Одна привычка: календарь за год (как у GitHub), серии, итоги по месяцам, заметки. */
export default function HabitDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { c, t } = useApp();
  const { data } = useFetch<Detail>(`/tracker/habits/${id}/detail/`);
  const scroll = useRef<ScrollView>(null);
  if (!data) return <Screen title="" back><Loading /></Screen>;
  const h = data.habit;
  const col = h.color;
  const shade = (lvl: number, skipped: boolean) => (skipped ? c.line : lvl <= 0 ? c.card2 : `${col}${['', '55', '88', 'bb', ''][lvl]}`);
  // сетка: колонки — недели, строки — дни недели (пн…вс)
  const first = new Date(data.cells[0].day);
  const pad = (first.getDay() + 6) % 7;
  const cells: (Cell | null)[] = [...Array(pad).fill(null), ...data.cells];
  const weeks: (Cell | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  const tile = (value: string, label: string, icon?: 'flame' | 'trophy', tint?: string) => (
    <Card style={{ flex: 1, minWidth: 140, gap: 2 }}>
      <Txt style={{ fontSize: 22, fontWeight: '800' }}>{icon ? <Icon name={icon} size={20} color={tint} /> : null}{icon ? ' ' : ''}{value}</Txt>
      <Txt kind="small">{label}</Txt>
    </Card>
  );
  return (
    <Screen title={h.title} back>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {tile(String(data.streak), h.per_week ? t('недель подряд') : t('дней подряд'), 'flame', '#f97316')}
        {tile(String(data.best), t('лучшая серия'), 'trophy', '#eab308')}
        {tile(String(data.done_days), t('дней выполнено'))}
        {h.kind === 'count' ? tile(String(data.total), h.unit || t('всего')) : null}
      </View>
      <Section title={t('Год')}>
        <Card style={{ padding: 12 }}>
          <ScrollView ref={scroll} horizontal showsHorizontalScrollIndicator={false} onContentSizeChange={() => scroll.current?.scrollToEnd({ animated: false })}>
            <View style={{ flexDirection: 'row', gap: 3 }}>
              {weeks.map((w, i) => (
                <View key={i} style={{ gap: 3 }}>
                  {w.map((cell, j) => <View key={j} style={{ width: 12, height: 12, borderRadius: 3, backgroundColor: cell ? shade(cell.level, cell.skipped) : 'transparent', opacity: cell && !cell.due ? 0.35 : 1 }} />)}
                </View>
              ))}
            </View>
          </ScrollView>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 10 }}>
            <Txt kind="small">{t('меньше')}</Txt>
            {[0, 1, 2, 3, 4].map((l) => <View key={l} style={{ width: 12, height: 12, borderRadius: 3, backgroundColor: shade(l, false) }} />)}
            <Txt kind="small">{t('больше')}</Txt>
          </View>
        </Card>
      </Section>
      <Section title={t('По месяцам')}>
        <Card style={{ gap: 8 }}>
          {data.months.map((m) => {
            const rate = m.due ? Math.round((100 * m.done) / m.due) : 0;
            return (
              <View key={m.month} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <Txt kind="small" style={{ width: 62 }}>{m.month.slice(5)}.{m.month.slice(0, 4)}</Txt>
                <View style={{ flex: 1, height: 8, borderRadius: 4, backgroundColor: c.card2, overflow: 'hidden' }}>
                  <View style={{ width: `${rate}%`, height: 8, borderRadius: 4, backgroundColor: col }} />
                </View>
                <Txt kind="small" style={{ width: 40, textAlign: 'right', fontWeight: '700' }}>{rate}%</Txt>
              </View>
            );
          })}
        </Card>
      </Section>
      {data.notes.length ? (
        <Section title={t('Заметки')}>
          <Card style={{ gap: 10 }}>
            {data.notes.map((n) => (
              <View key={n.day}>
                <Txt style={{ fontWeight: '600' }}>{n.note}</Txt>
                <Txt kind="small">{n.day.split('-').reverse().join('.')}</Txt>
              </View>
            ))}
          </Card>
        </Section>
      ) : null}
      {h.can_edit ? <Button kind="soft" icon="pencil-outline" title={t('Изменить привычку')} onPress={() => router.push({ pathname: '/habits/edit', params: { id: String(h.id) } })} /> : null}
    </Screen>
  );
}
