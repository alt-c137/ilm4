import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Modal, Pressable, TextInput, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, Empty, ErrorBox, Icon, Loading, Press, Screen, Section, Sheet, Txt } from '@/ui/kit';
import { HabitIcon, HabitRow, isoDay, PARTS, Ring, type Habit } from '@/ui/tracker';
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
  const [more, setMore] = useState<Habit | null>(null);
  const [add, setAdd] = useState(false);
  const [noteFor, setNoteFor] = useState<Habit | null>(null);
  const [note, setNote] = useState('');
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
  const log = async (h: Habit, body: Record<string, unknown>) => {
    try {
      await api(`/tracker/habits/${h.id}/log/`, { body: { day, ...body } });
      reload(true);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
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
          <Pressable onPress={() => setAdd(true)} hitSlop={8} accessibilityLabel={t('Добавить')}><Icon name="add-circle" size={28} color={c.accent} /></Pressable>
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
            {items.map((h, i) => {
              const head = i === 0 ? !!h.part : items[i - 1].part !== h.part;
              const part = PARTS.find((p) => p.key === (h.part ?? ''));
              return (
                <View key={h.id} style={{ gap: 8 }}>
                  {head && part ? <Txt kind="label" style={{ marginTop: i ? 8 : 0, paddingHorizontal: 4 }}><Icon name={part.icon} size={13} color={c.inkSoft} /> {t(part.label)}</Txt> : null}
                  <HabitRow h={h} canMark={canMark} onToggle={(x) => mark(x)} onStep={(x, by) => mark(x, Math.max(0, x.value + by))} onEdit={edit} onMore={setMore} />
                </View>
              );
            })}
          </View>
        </>
      ) : (
        <Empty icon="checkmark-circle-outline" title={data.habits_total ? t('На этот день ничего не запланировано') : t('Начните с одной привычки')}
          text={t('Таблетки, вода, чтение, зарядка, слова на арабском — что угодно. Отмечайте каждый день и смотрите, как растёт серия.')}
          action={data.habits_total ? <Button small kind="soft" title={t('Добавить')} icon="add" onPress={() => setAdd(true)} /> : (
            <View style={{ gap: 8 }}>
              <Button small title={t('Выбрать из готовых')} icon="star" onPress={() => router.push('/habits/templates')} />
              <Button small kind="soft" title={t('Своя привычка')} icon="add" onPress={() => router.push('/habits/edit')} />
            </View>)} />
      )}
      {items.length ? <Button small kind="soft" icon="add" title={t('Добавить')} onPress={() => setAdd(true)} /> : null}

      <Section title={t('Вместе')}>
        {(data?.boards ?? []).map((b) => (
          <Press key={b.id} onPress={() => router.push(`/habits/board/${b.id}`)} scale={0.985}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: c.card, borderRadius: 18, padding: 14 }}>
            <HabitIcon value={b.emoji} size={26} />
            <View style={{ flex: 1 }}>
              <Txt style={{ fontWeight: '700', fontSize: 15.5 }} numberOfLines={1}>{b.title}</Txt>
              <Txt kind="small">{t('участников: {n}', { n: b.members })}{b.compete ? <>{' · '}<Icon name="trophy" size={12.5} color="#eab308" /></> : null}</Txt>
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
      {/* одна кнопка «Добавить» — выбор, что именно */}
      <Sheet open={add} onClose={() => setAdd(false)} title={t('Добавить')} items={[
        { icon: 'repeat-outline', title: t('Привычка'), subtitle: t('Повторяется: каждый день или по дням недели'), onPress: () => router.push('/habits/edit') },
        { icon: 'today-outline', title: t('Дело на день'), subtitle: t('Один раз — на выбранный день'), onPress: () => router.push({ pathname: '/habits/edit', params: { once: day } }) },
        { icon: 'star-outline', title: t('Готовые привычки'), subtitle: t('Намаз, Коран, вода, таблетки…'), onPress: () => router.push('/habits/templates') },
        { icon: 'people-outline', title: t('Общий трекер'), subtitle: t('С семьёй, друзьями, напарниками'), onPress: () => router.push('/habits/board-new') },
      ]} />
      <Sheet open={!!more} onClose={() => setMore(null)} title={more ? more.title : ''} items={more ? [
        ...(canMark ? [{ icon: more.skipped ? 'refresh-outline' as const : 'bed-outline' as const, title: more.skipped ? t('Отменить пропуск') : t('Пропуск по уважительной причине'),
          subtitle: t('Болезнь, дорога — день не считается, серия не рвётся'), onPress: () => log(more, { skip: !more.skipped }) },
          { icon: 'pencil-outline' as const, title: t('Заметка к этому дню'), subtitle: more.log_note || undefined,
            onPress: () => { setNote(more.log_note ?? ''); setTimeout(() => setNoteFor(more), 300); } }] : []),
        { icon: 'calendar-outline', title: t('Календарь и история'), onPress: () => router.push(`/habits/${more.id}`) },
        ...(more.can_edit ? [{ icon: 'settings-outline' as const, title: t('Изменить'), onPress: () => edit(more) }] : []),
      ] : []} />
      <Modal visible={!!noteFor} transparent animationType="fade" onRequestClose={() => setNoteFor(null)}>
        <Pressable style={{ flex: 1, backgroundColor: c.overlay, justifyContent: 'center', padding: 24 }} onPress={() => setNoteFor(null)}>
          <Pressable style={{ backgroundColor: c.card, borderRadius: 20, padding: 16, gap: 12 }} onPress={() => {}}>
            <Txt kind="h3">{t('Заметка к этому дню')}</Txt>
            <TextInput value={note} onChangeText={setNote} autoFocus maxLength={200} multiline placeholder={t('Например: принял после еды')} placeholderTextColor={c.inkSoft}
              style={{ minHeight: 70, backgroundColor: c.card2, borderRadius: 14, padding: 12, fontSize: 16, color: c.ink, textAlignVertical: 'top' }} />
            <Button title={t('Сохранить')} onPress={() => { const h = noteFor; setNoteFor(null); if (h) log(h, { note }); }} />
          </Pressable>
        </Pressable>
      </Modal>
    </Screen>
  );
}
