import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, Icon, Loading, Screen, Section, Txt } from '@/ui/kit';
import { HabitIcon } from '@/ui/tracker';
import { useFetch } from '@/ui/useFetch';

type Tpl = { key: string; group: string; title: string; emoji: string; color: string; kind: string; target: number; unit: string;
  per_week: number; days: string; reminders: string; note: string };

/** Готовые привычки — одно нажатие: намазы, азкары, Коран, пост, вода, таблетки, арабский, чтение. ?board= — в общий трекер. */
export default function Templates() {
  const { board } = useLocalSearchParams<{ board?: string }>();
  const { c, t } = useApp();
  const { data } = useFetch<{ groups: { key: string; name: string }[]; items: Tpl[] }>('/tracker/templates/');
  const [added, setAdded] = useState<string[]>([]);
  const add = async (x: Tpl) => {
    try {
      await api('/tracker/templates/', { body: { key: x.key, tz_offset: -new Date().getTimezoneOffset(), ...(board ? { board } : {}) } });
      setAdded((old) => [...old, x.key]);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const how = (x: Tpl) => [
    x.kind === 'count' ? `${x.target} ${x.unit} ${t('в день')}` : x.per_week ? t('{n} раз в неделю', { n: x.per_week }) : x.days === '14' ? t('пн и чт') : t('каждый день'),
    x.reminders ? x.reminders.replace(/,/g, ', ') : '', x.note,
  ].filter(Boolean).join(' · ');
  return (
    <Screen title={t('Готовые привычки')} back>
      <Txt kind="muted">{t('Одно нажатие — и привычка в списке. Время, цель и напоминания потом можно поменять.')}</Txt>
      {!data ? <Loading /> : data.groups.map((g) => (
        <Section key={g.key} title={g.name}>
          <Card style={{ paddingVertical: 4 }}>
            {data.items.filter((x) => x.group === g.key).map((x, i) => {
              const done = added.includes(x.key);
              return (
                <View key={x.key} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
                  <View style={{ width: 42, height: 42, borderRadius: 13, backgroundColor: `${x.color}26`, alignItems: 'center', justifyContent: 'center' }}>
                    <HabitIcon value={x.emoji} size={22} color={x.color} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Txt style={{ fontWeight: '700' }}>{x.title}</Txt>
                    <Txt kind="small" numberOfLines={2}>{how(x)}</Txt>
                  </View>
                  {done ? <Icon name="checkmark-circle" size={26} color={c.ok} /> : <Button small title={t('Добавить')} onPress={() => add(x)} />}
                </View>
              );
            })}
          </Card>
        </Section>
      ))}
      <Button kind="soft" icon="add" title={t('Своя привычка')} onPress={() => router.replace({ pathname: '/habits/edit', params: board ? { board } : {} })} />
    </Screen>
  );
}
