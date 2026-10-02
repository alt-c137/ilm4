import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { useApp } from '@/state/app';
import { Card, ErrorBox, Loading, Press, Screen, Section, Segmented, Txt } from '@/ui/kit';
import { type Habit } from '@/ui/tracker';
import { useFetch } from '@/ui/useFetch';

type Stats = { days: { day: string; done: number; total: number }[]; rate: number; done: number; total: number; perfect_days: number; period: number;
  habits: { id: number; title: string; emoji: string; color: string; done: number; total: number; rate: number; streak: number; best: number; sum: number; unit: string; cells: number[] }[] };

/** Графики трекера: выполнение по дням, по привычкам, серии. */
export default function HabitStats() {
  const { c, t } = useApp();
  const [period, setPeriod] = useState<'7' | '30' | '90'>('30');
  const { data, loading, error, reload } = useFetch<Stats>(`/tracker/stats/?days=${period}`);
  const all = useFetch<{ items: Habit[] }>('/tracker/habits/');
  const archived = (all.data?.items ?? []).filter((h) => h.archived);
  const top = Math.max(1, ...(data?.days ?? []).map((d) => d.total));

  return (
    <Screen back title={t('Графики')} onRefresh={reload} refreshing={loading && !!data}>
      <Segmented value={period} onChange={setPeriod} options={[{ key: '7', label: t('{n} дней', { n: 7 }) }, { key: '30', label: t('{n} дней', { n: 30 }) }, { key: '90', label: t('{n} дней', { n: 90 }) }]} />
      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : (
        <>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {[[`${data.rate}%`, t('выполнено')], [String(data.done), t('отметок')], [String(data.perfect_days), t('дней на 100%')]].map(([v, l]) => (
              <Card key={l} style={{ flex: 1, alignItems: 'center', paddingVertical: 14, paddingHorizontal: 4 }}>
                <Txt style={{ fontSize: 23, fontWeight: '800' }} color={c.accent}>{v}</Txt>
                <Txt kind="small" style={{ fontSize: 12, textAlign: 'center' }}>{l}</Txt>
              </Card>
            ))}
          </View>
          <Card style={{ gap: 10 }}>
            <Txt kind="h3">{t('По дням')}</Txt>
            <View style={{ flexDirection: 'row', alignItems: 'flex-end', height: 140, gap: data.days.length > 40 ? 1 : 3 }}>
              {data.days.map((d) => (
                <View key={d.day} style={{ flex: 1, height: '100%', justifyContent: 'flex-end' }}>
                  <View style={{ height: `${Math.max(3, (100 * d.total) / top)}%`, backgroundColor: c.line, borderRadius: 4, justifyContent: 'flex-end', overflow: 'hidden' }}>
                    <View style={{ height: `${d.total ? (100 * d.done) / d.total : 0}%`, backgroundColor: c.accent, borderRadius: 4 }} />
                  </View>
                </View>
              ))}
            </View>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <Txt kind="small" style={{ fontSize: 11 }}>{data.days[0]?.day.slice(5).split('-').reverse().join('.')}</Txt>
              <Txt kind="small" style={{ fontSize: 11 }}>{t('сегодня')}</Txt>
            </View>
          </Card>
          {data.habits.length ? (
            <Card style={{ gap: 4 }}>
              <Txt kind="h3">{t('По привычкам')}</Txt>
              {data.habits.map((h, i) => (
                <View key={h.id} style={{ gap: 6, paddingVertical: 10, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 10 }}>
                    <Txt style={{ flex: 1, fontWeight: '700' }} numberOfLines={1}>{h.emoji} {h.title}</Txt>
                    <Txt style={{ fontWeight: '800' }} color={h.color}>{h.rate}%</Txt>
                  </View>
                  <View style={{ height: 7, borderRadius: 4, backgroundColor: c.line, overflow: 'hidden' }}><View style={{ width: `${h.rate}%`, height: 7, borderRadius: 4, backgroundColor: h.color }} /></View>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 3 }}>
                    {h.cells.map((on, n) => <View key={n} style={{ width: 11, height: 11, borderRadius: 3, backgroundColor: on ? h.color : c.line }} />)}
                  </View>
                  <Txt kind="small" style={{ fontSize: 12 }}>
                    {t('{a} из {b}', { a: h.done, b: h.total })}{h.sum ? ` · ${t('всего')} ${h.sum} ${h.unit}` : ''} · 🔥 {t('серия')} {h.streak} · {t('лучшая')} {h.best}</Txt>
                </View>
              ))}
            </Card>
          ) : <Txt kind="muted" style={{ textAlign: 'center', padding: 20 }}>{t('Пока нечего показывать: добавьте привычку и отмечайте её несколько дней.')}</Txt>}
        </>
      )}
      {archived.length ? (
        <Section title={t('Архив')}>
          <Card style={{ paddingVertical: 4 }}>
            {archived.map((h, i) => (
              <Press key={h.id} onPress={() => router.push({ pathname: '/habits/edit', params: { id: String(h.id) } })}
                style={{ paddingVertical: 11, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
                <Txt style={{ fontWeight: '600' }}>{h.emoji} {h.title}</Txt>
              </Press>
            ))}
          </Card>
        </Section>
      ) : null}
    </Screen>
  );
}
