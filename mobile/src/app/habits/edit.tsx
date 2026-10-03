import DateTimePicker, { DateTimePickerAndroid } from '@react-native-community/datetimepicker';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, Pressable, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Chip, Field, Icon, Screen, Section, Segmented, Sheet, Txt } from '@/ui/kit';
import { COLORS, HabitIcon, ICONS, isoDay, PARTS, type Habit } from '@/ui/tracker';
import { useFetch } from '@/ui/useFetch';

const WD = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

/** Новая привычка или дело — или правка существующей (?id=). ?board= — в общий трекер, ?once=день — разовое дело. */
export default function HabitEdit() {
  const params = useLocalSearchParams<{ id?: string; board?: string; once?: string }>();
  const { c, t } = useApp();
  const { data: old } = useFetch<Habit>(params.id ? `/tracker/habits/${params.id}/` : null);
  const { data: day } = useFetch<{ boards: { id: number; title: string; emoji: string }[] }>(!params.id ? '/tracker/' : null);
  const [title, setTitle] = useState('');
  const [emoji, setEmoji] = useState(ICONS[0]);
  const [color, setColor] = useState(COLORS[0]);
  const [kind, setKind] = useState<'check' | 'count'>('check');
  const [target, setTarget] = useState('8');
  const [unit, setUnit] = useState('');
  const [repeat, setRepeat] = useState<'days' | 'week' | 'once'>(params.once ? 'once' : 'days');
  const [perWeek, setPerWeek] = useState(3);
  const [part, setPart] = useState<'' | 'morning' | 'day' | 'evening'>('');
  const [times, setTimes] = useState<string[]>([]);
  const [note, setNote] = useState('');
  const [timeAt, setTimeAt] = useState<number>(-1);          // какое напоминание меняем (−1 — новое)
  const [days, setDays] = useState('1234567');
  const [once, setOnce] = useState(params.once || isoDay());
  const [remind, setRemind] = useState('');
  const [board, setBoard] = useState<number | null>(params.board ? Number(params.board) : null);
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState<'board' | 'more' | null>(null);
  const [picker, setPicker] = useState<'time' | 'date' | null>(null);

  useEffect(() => {
    if (!old) return;
    /* eslint-disable react-hooks/set-state-in-effect -- заполняем форму загруженной привычкой */
    setTitle(old.title); setEmoji(old.emoji); setColor(old.color); setKind(old.kind); setTarget(String(old.target)); setUnit(old.unit);
    setRepeat(old.once_on ? 'once' : old.per_week ? 'week' : 'days'); setDays(old.days); if (old.once_on) setOnce(old.once_on); setRemind(old.remind_at); setBoard(old.board);
    setPerWeek(old.per_week || 3); setPart(old.part ?? ''); setTimes(old.reminders ?? (old.remind_at ? [old.remind_at] : [])); setNote(old.note ?? '');
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [old]);

  const fail = (e: unknown) => Alert.alert((e as ApiError).message);
  const body = () => ({ title, emoji, color, kind, target: Number(target) || 1, unit, days, once_on: repeat === 'once' ? once : '',
    per_week: repeat === 'week' ? perWeek : 0, part, note, reminders: times.join(','),
    tz_offset: -new Date().getTimezoneOffset(), day: isoDay() });
  const save = async () => {
    setBusy(true);
    try {
      if (params.id) await api(`/tracker/habits/${params.id}/`, { body: body() });
      else await api('/tracker/habits/new/', { body: { ...body(), ...(board ? { board } : {}) } });
      router.back();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };
  const archive = async () => { try { await api(`/tracker/habits/${params.id}/`, { body: { archived: old?.archived ? '' : '1' } }); router.back(); } catch (e) { fail(e); } };
  const remove = () => Alert.alert(t('Удалить вместе со всеми отметками?'), undefined, [
    { text: t('Отмена'), style: 'cancel' },
    { text: t('Удалить'), style: 'destructive', onPress: async () => { try { await api(`/tracker/habits/${params.id}/`, { method: 'DELETE' }); router.back(); } catch (e) { fail(e); } } }]);

  const openPicker = (what: 'time' | 'date') => {
    const base = new Date();
    const cur = timeAt >= 0 ? times[timeAt] : remind;
    if (what === 'time' && cur) { const [h, m] = cur.split(':').map(Number); base.setHours(h, m, 0, 0); }
    if (what === 'date') { const [y, m, d] = once.split('-').map(Number); base.setFullYear(y, m - 1, d); }
    const apply = (d: Date) => (what === 'time' ? putTime(`${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`) : setOnce(isoDay(d)));
    if (Platform.OS === 'android') DateTimePickerAndroid.open({ value: base, mode: what, is24Hour: true, onChange: (e, d) => { if (e.type === 'set' && d) apply(d); } });
    else if (Platform.OS === 'ios') setPicker(what);
    else Alert.alert(t('Выбор времени — в приложении на телефоне.'));
  };
  // напоминания: несколько в день (таблетки 08:00, 14:00, 20:00)
  function putTime(v: string) {
    setTimes((old) => {
      const next = timeAt >= 0 ? old.map((x, i) => (i === timeAt ? v : x)) : [...old, v];
      return [...new Set(next)].sort().slice(0, 6);
    });
  }
  const toggleDay = (k: string) => setDays((d) => { const next = d.includes(k) ? d.replace(k, '') : [...d, k].sort().join(''); return next || d; });
  const boards = day?.boards ?? [];
  const boardName = board ? (boards.find((b) => b.id === board)?.title ?? old?.board_title ?? t('Общий трекер')) : t('Только у меня (личное)');

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen back title={params.id ? t('Изменить') : t('Новая привычка или дело')}
        right={params.id ? <Pressable onPress={() => setMenu('more')} hitSlop={10}><Icon name="ellipsis-vertical" size={21} /></Pressable> : undefined}>
        <Field label={t('Что нужно делать')} value={title} onChangeText={setTitle} maxLength={80} placeholder={t('Например: выпить витамины')} autoFocus={!params.id} />
        <Section title={t('Значок')}>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {ICONS.map((e) => (
              <Pressable key={e} onPress={() => setEmoji(e)} style={{ width: 42, height: 42, borderRadius: 13, alignItems: 'center', justifyContent: 'center',
                backgroundColor: emoji === e ? c.accentSoft : c.card, borderWidth: 2, borderColor: emoji === e ? c.accent : 'transparent' }}>
                <HabitIcon value={e} size={22} color={emoji === e ? c.accentD : c.ink} />
              </Pressable>
            ))}
          </View>
        </Section>
        <Section title={t('Цвет')}>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
            {COLORS.map((col) => <Pressable key={col} onPress={() => setColor(col)} style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: col, borderWidth: color === col ? 3 : 0, borderColor: c.ink }} />)}
          </View>
        </Section>
        <Section title={t('Как отмечать')}>
          <Segmented value={kind} onChange={setKind} options={[{ key: 'check', label: t('Сделал — галочка') }, { key: 'count', label: t('Считать количество') }]} />
          {kind === 'count' ? (
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <View style={{ flex: 1 }}><Field label={t('Цель в день')} value={target} onChangeText={(x) => setTarget(x.replace(/\D/g, ''))} keyboardType="number-pad" maxLength={6} /></View>
              <View style={{ flex: 1.4 }}><Field label={t('Чего')} value={unit} onChangeText={setUnit} maxLength={16} placeholder={t('стаканов, страниц, минут')} /></View>
            </View>
          ) : null}
        </Section>
        <Section title={t('Когда')}>
          <Segmented value={repeat} onChange={setRepeat} options={[{ key: 'days', label: t('По дням') }, { key: 'week', label: t('N раз в неделю') }, { key: 'once', label: t('Один раз') }]} />
          {repeat === 'week' ? (
            <View style={{ gap: 6 }}>
              <View style={{ flexDirection: 'row', gap: 6 }}>
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <Pressable key={n} onPress={() => setPerWeek(n)} style={{ flex: 1, paddingVertical: 10, borderRadius: 12, alignItems: 'center', backgroundColor: perWeek === n ? c.accent : c.card }}>
                    <Txt style={{ fontWeight: '800' }} color={perWeek === n ? '#fff' : c.ink}>{n}</Txt>
                  </Pressable>
                ))}
              </View>
              <Txt kind="small">{t('В любые дни — главное, набрать за неделю. Серия считается в неделях.')}</Txt>
            </View>
          ) : repeat === 'days' ? (
            <View style={{ flexDirection: 'row', gap: 5 }}>
              {WD.map((n, i) => {
                const k = String(i + 1);
                const on = days.includes(k);
                return (
                  <Pressable key={k} onPress={() => toggleDay(k)} style={{ flex: 1, paddingVertical: 10, borderRadius: 12, alignItems: 'center', backgroundColor: on ? c.accent : c.card }}>
                    <Txt kind="small" style={{ fontWeight: '700' }} color={on ? '#fff' : c.inkSoft}>{t(n)}</Txt>
                  </Pressable>
                );
              })}
            </View>
          ) : <Chip icon="calendar-outline" label={once.split('-').reverse().join('.')} onPress={() => openPicker('date')} />}
        </Section>
        <Section title={t('Время дня')}>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {PARTS.map((p) => <Chip key={p.key || 'any'} label={t(p.label)} on={part === p.key} onPress={() => setPart(p.key)} />)}
          </View>
        </Section>
        <Section title={t('Напоминания')}>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
            {times.map((tm, i) => (
              <View key={tm} style={{ flexDirection: 'row', alignItems: 'center', gap: 2 }}>
                <Chip icon="alarm-outline" label={tm} on onPress={() => { setTimeAt(i); openPicker('time'); }} />
                <Pressable onPress={() => setTimes((old) => old.filter((x) => x !== tm))} hitSlop={8}><Icon name="close-circle" size={20} color={c.inkSoft} /></Pressable>
              </View>
            ))}
            {times.length < 6 ? <Chip icon="add" label={times.length ? t('ещё') : t('Добавить напоминание')} onPress={() => { setTimeAt(-1); openPicker('time'); }} /> : null}
          </View>
          <Txt kind="small">{t('Например, таблетки — 08:00, 14:00 и 20:00. До шести напоминаний в день.')}</Txt>
        </Section>
        <Field label={t('Заметка (необязательно)')} value={note} onChangeText={setNote} maxLength={200} placeholder={t('Например: 1 таблетка после еды')} />
        {!params.id && boards.length ? (
          <Section title={t('Где вести')}>
            <Chip icon={board ? 'people-outline' : 'lock-closed-outline'} label={boardName} onPress={() => setMenu('board')} />
          </Section>
        ) : null}
        {picker ? (
          <View style={{ backgroundColor: c.card, borderRadius: 18, padding: 8 }}>
            <DateTimePicker value={new Date()} mode={picker} display="spinner" onChange={(_e, d) => {
              if (!d) return;
              if (picker === 'time') putTime(`${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`); else setOnce(isoDay(d));
            }} />
            <Button small kind="soft" title={t('Готово')} onPress={() => setPicker(null)} />
          </View>
        ) : null}
        <Button title={t('Сохранить')} onPress={save} loading={busy} disabled={title.trim().length < 2} />
      </Screen>
      <Sheet open={menu === 'board'} onClose={() => setMenu(null)} title={t('Где вести')} items={[
        { icon: 'lock-closed-outline', title: t('Только у меня (личное)'), on: !board, onPress: () => setBoard(null) },
        ...boards.map((b) => ({ title: b.title, on: board === b.id, onPress: () => setBoard(b.id) }))]} />
      <Sheet open={menu === 'more'} onClose={() => setMenu(null)} items={[
        { icon: 'archive-outline', title: old?.archived ? t('Вернуть из архива') : t('В архив'), subtitle: t('Отметки сохранятся'), onPress: archive },
        { icon: 'trash-outline', danger: true, title: t('Удалить'), onPress: remove }]} />
    </KeyboardAvoidingView>
  );
}
