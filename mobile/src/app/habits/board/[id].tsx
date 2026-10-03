import * as Clipboard from 'expo-clipboard';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import DateTimePicker, { DateTimePickerAndroid } from '@react-native-community/datetimepicker';
import { Alert, Platform, Pressable, Share, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Button, Card, Empty, ErrorBox, Icon, Loading, Screen, Section, Segmented, Sheet, Txt, type SheetItem } from '@/ui/kit';
import { HabitIcon, HabitRow, isoDay, type Habit } from '@/ui/tracker';
import { useFetch } from '@/ui/useFetch';

type Man = { id: number; name: string; avatar: string; points: number; total: number; rate: number; me: boolean; owner: boolean; place?: number };
type Board = { id: number; title: string; emoji: string; compete: boolean; members: number; owner: boolean; day: string; today: string;
  items: Habit[]; people: Man[]; period: number; invite_link: string;
  ends_on?: string; days_left?: number | null; finished?: boolean; chat?: number | null;
  activity?: { name: string; user: number; habit: string; emoji: string; value: number; unit: string; done: boolean; day: string; me: boolean }[] };

/** Общий трекер: привычки с отметками каждого, таблица (если включено соревнование), приглашение. */
export default function BoardScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { c, t } = useApp();
  const [period, setPeriod] = useState<'7' | '30'>('7');
  const day = isoDay();
  const { data, setData, loading, error, reload } = useFetch<Board>(`/tracker/boards/${id}/?day=${day}&days=${period}`);
  const [menu, setMenu] = useState(false);
  const [iosDate, setIosDate] = useState<Date | null>(null);
  useFocusEffect(useCallback(() => { reload(true); }, [reload]));

  if (!data) return <Screen back title="">{loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />}</Screen>;
  const fail = (e: unknown) => Alert.alert((e as ApiError).message);
  const post = async (body: Record<string, unknown>) => {
    try {
      const r = await api<Board & { left?: boolean }>(`/tracker/boards/${id}/`, { body: { ...body, day, days: Number(period) } });
      if (r.left) return router.back();
      setData(r);
    } catch (e) {
      fail(e);
    }
  };
  const mark = async (h: Habit, value?: number) => {
    try {
      await api(`/tracker/habits/${h.id}/log/`, { body: value === undefined ? { day } : { day, value } });
      reload(true);
    } catch (e) {
      fail(e);
    }
  };
  const openChat = async () => {
    try {
      const r = await api<{ thread: number }>(`/tracker/boards/${id}/chat/`, { body: {} });
      router.push(`/chat/${r.thread}`);
    } catch (e) {
      fail(e);
    }
  };
  function pickEnd() {
    const base = data!.ends_on ? new Date(data!.ends_on) : new Date();
    if (!data!.ends_on) base.setDate(base.getDate() + 30);
    if (Platform.OS === 'android') DateTimePickerAndroid.open({ value: base, mode: 'date', minimumDate: new Date(), onChange: (e, d) => { if (e.type === 'set' && d) post({ ends_on: isoDay(d) }); } });
    else if (Platform.OS === 'ios') setIosDate(base);
  }
  const confirm = (title: string, run: () => void) => Alert.alert(title, undefined, [{ text: t('Отмена'), style: 'cancel' }, { text: t('Да'), style: 'destructive', onPress: run }]);
  const items: SheetItem[] = data.owner ? [
    { icon: 'trophy-outline', title: data.compete ? t('Выключить соревнование') : t('Включить соревнование'), subtitle: t('Таблица: кто сколько выполнил за период'), onPress: () => post({ compete: data.compete ? '' : '1' }) },
    { icon: 'calendar-outline', title: data.ends_on ? t('Соревнование до {d}', { d: data.ends_on.split('-').reverse().join('.') }) : t('Срок соревнования'),
      subtitle: t('После этой даты будет виден победитель'), onPress: pickEnd },
    ...(data.ends_on ? [{ icon: 'close-circle-outline' as const, title: t('Без срока'), onPress: () => post({ ends_on: '' }) }] : []),
    { icon: 'refresh-outline', title: t('Сделать новую ссылку'), subtitle: t('Старая перестанет работать'), onPress: () => confirm(t('Старая ссылка перестанет работать. Продолжить?'), () => post({ new_link: 1 })) },
    { icon: 'trash-outline', danger: true, title: t('Удалить трекер'), subtitle: t('У всех участников, вместе с отметками'),
      onPress: () => confirm(t('Удалить трекер у всех участников?'), async () => { try { await api(`/tracker/boards/${id}/`, { method: 'DELETE' }); router.back(); } catch (e) { fail(e); } }) },
  ] : [
    { icon: 'exit-outline', danger: true, title: t('Выйти из трекера'), subtitle: t('Ваши отметки здесь удалятся'), onPress: () => confirm(t('Выйти из трекера?'), () => post({ leave: 1 })) },
  ];
  const MEDAL = ['#eab308', '#94a3b8', '#c2793f'];

  return (
    <Screen back title={data.title} onRefresh={reload} refreshing={loading}
      right={
        <View style={{ flexDirection: 'row', gap: 14, alignItems: 'center' }}>
          <Pressable onPress={() => router.push({ pathname: '/habits/edit', params: { board: String(id) } })} hitSlop={8} accessibilityLabel={t('Добавить привычку')}><Icon name="add-circle" size={27} color={c.accent} /></Pressable>
          <Pressable onPress={() => setMenu(true)} hitSlop={8} accessibilityLabel={t('Ещё')}><Icon name="ellipsis-vertical" size={21} /></Pressable>
        </View>}>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Button small kind="soft" icon="chatbubbles-outline" title={t('Чат трекера')} style={{ flex: 1 }} onPress={openChat} />
        <Button small kind="soft" icon="star-outline" title={t('Готовые')} style={{ flex: 1 }} onPress={() => router.push({ pathname: '/habits/templates', params: { board: String(id) } })} />
      </View>
      {data.ends_on ? (
        <Card soft style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <Icon name={data.finished ? 'trophy' : 'hourglass-outline'} size={22} color={data.finished ? '#eab308' : c.accentD} />
          <Txt style={{ flex: 1, fontWeight: '700' }}>{data.finished
            ? (data.people[0] ? t('Победитель: {name} — {n} отметок', { name: data.people[0].name, n: data.people[0].points }) : t('Соревнование завершено'))
            : t('До конца соревнования дней: {n}', { n: data.days_left ?? 0 })}</Txt>
        </Card>
      ) : null}
      {data.items.length ? (
        <View style={{ gap: 8 }}>
          {data.items.map((h) => <HabitRow key={h.id} h={h} hideBoard canMark onToggle={(x) => mark(x)} onStep={(x, by) => mark(x, Math.max(0, x.value + by))}
            onEdit={(x) => router.push({ pathname: '/habits/edit', params: { id: String(x.id) } })} />)}
        </View>
      ) : (
        <Empty icon="people-outline" title={t('Пока пусто')} text={t('Добавьте первую общую привычку — её увидят все участники, а отмечать каждый будет сам.')}
          action={<Button small icon="add" title={t('Добавить привычку')} onPress={() => router.push({ pathname: '/habits/edit', params: { board: String(id) } })} />} />
      )}

      <Section title={data.compete ? t('Таблица') : t('Участники')}>
        <Segmented value={period} onChange={setPeriod} options={[{ key: '7', label: t('{n} дней', { n: 7 }) }, { key: '30', label: t('{n} дней', { n: 30 }) }]} />
        <View style={{ backgroundColor: c.card, borderRadius: 20, overflow: 'hidden' }}>
          {data.people.map((p, i) => (
            <Pressable key={p.id} onPress={() => router.push(`/user/${p.id}`)}
              onLongPress={data.owner && !p.me ? () => confirm(t('Убрать из трекера?'), () => post({ remove: p.id })) : undefined}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, paddingHorizontal: 14, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line, backgroundColor: p.me ? c.accentSoft : 'transparent' }}>
              {data.compete ? <View style={{ width: 26, alignItems: 'center' }}>{p.place && p.place <= 3 ? <Icon name="medal" size={20} color={MEDAL[p.place - 1]} /> : <Txt style={{ fontSize: 16, fontWeight: '800' }} color={c.inkSoft}>{p.place ?? ''}</Txt>}</View> : null}
              <Avatar uri={p.avatar} name={p.name} size={38} hue={p.id} />
              <View style={{ flex: 1, gap: 5 }}>
                <Txt style={{ fontWeight: '700' }} numberOfLines={1}>{p.name}{p.owner ? ` · ${t('владелец')}` : ''}</Txt>
                <View style={{ height: 6, borderRadius: 3, backgroundColor: c.line, overflow: 'hidden' }}><View style={{ width: `${p.rate}%`, height: 6, backgroundColor: c.accent, borderRadius: 3 }} /></View>
              </View>
              <Txt style={{ fontWeight: '800', fontSize: 16 }}>{p.points}<Txt kind="small">/{p.total}</Txt></Txt>
            </Pressable>
          ))}
        </View>
        {data.owner ? <Txt kind="small" style={{ paddingHorizontal: 4 }}>{t('Убрать участника — долгое нажатие на его строку.')}</Txt> : null}
      </Section>

      {data.activity?.length ? (
        <Section title={t('Что нового')}>
          <Card style={{ gap: 10 }}>
            {data.activity.slice(0, 10).map((a, i) => (
              <View key={`${a.user}${a.habit}${a.day}${i}`} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <View style={{ width: 28, alignItems: 'center' }}><HabitIcon value={a.emoji} size={20} /></View>
                <View style={{ flex: 1 }}>
                  <Txt style={{ fontWeight: '600' }} numberOfLines={1}>{a.me ? t('Вы') : a.name} · {a.habit}{a.unit ? ` — ${a.value} ${a.unit}` : ''}{a.done ? ' ✓' : ''}</Txt>
                  <Txt kind="small">{a.day.split('-').reverse().join('.')}</Txt>
                </View>
              </View>
            ))}
          </Card>
        </Section>
      ) : null}

      <Section title={t('Позвать людей')}>
        <Card style={{ gap: 10 }}>
          <Txt selectable style={{ fontWeight: '600' }}>{data.invite_link.replace(/^https?:\/\//, '')}</Txt>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <Button small kind="soft" style={{ flex: 1 }} icon="copy-outline" title={t('Копировать')} onPress={async () => { await Clipboard.setStringAsync(data.invite_link); Alert.alert(t('Скопировано')); }} />
            <Button small kind="soft" style={{ flex: 1 }} icon="share-outline" title={t('Поделиться')} onPress={() => Share.share({ message: `${data.title}\n${data.invite_link}` })} />
          </View>
        </Card>
      </Section>
      <Sheet open={menu} onClose={() => setMenu(false)} title={data.title} items={items} />
      {iosDate ? (
        <Card style={{ gap: 8 }}>
          <DateTimePicker value={iosDate} mode="date" display="inline" minimumDate={new Date()} onChange={(_e, d) => { if (d) setIosDate(d); }} />
          <Button title={t('Готово')} onPress={() => { const d = iosDate; setIosDate(null); post({ ends_on: isoDay(d) }); }} />
        </Card>
      ) : null}
    </Screen>
  );
}
