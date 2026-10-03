/** Трекер привычек: общие части экранов — строка привычки с отметкой и кольцо выполнения. */
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import * as Haptics from 'expo-haptics';
import { Pressable, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

import { useApp } from '@/state/app';

import { Icon, Txt } from './kit';

export type Habit = {
  id: number; title: string; emoji: string; color: string; kind: 'check' | 'count'; target: number; unit: string; days: string;
  once_on: string; remind_at: string; board: number | null; board_title: string; value: number; done: boolean; due: boolean;
  streak: number; best: number; can_edit: boolean; archived: boolean; who?: { id: number; name: string; done: boolean }[];
  part?: '' | 'morning' | 'day' | 'evening'; per_week?: number; week_done?: number; skipped?: boolean; note?: string; log_note?: string;
  reminders?: string[];
};
export const PARTS: { key: '' | 'morning' | 'day' | 'evening'; label: string; icon: 'time-outline' | 'sunny-outline' | 'partly-sunny-outline' | 'moon-outline' }[] = [
  { key: '', label: 'В любое время', icon: 'time-outline' }, { key: 'morning', label: 'Утро', icon: 'sunny-outline' },
  { key: 'day', label: 'День', icon: 'partly-sunny-outline' }, { key: 'evening', label: 'Вечер', icon: 'moon-outline' }];
/** Значки привычек — ключи те же, что на сайте (тег hicon); эмодзи в интерфейсе не используем. */
const HABIT_ICON: Record<string, keyof typeof MaterialCommunityIcons.glyphMap> = {
  'h-check': 'check-circle-outline', 'h-pill': 'pill', 'h-water': 'water-outline', 'h-quran': 'book-open-page-variant-outline', 'h-mosque': 'mosque',
  'h-dua': 'hands-pray', 'h-run': 'run', 'h-walk': 'walk', 'h-sport': 'dumbbell', 'h-mind': 'meditation', 'h-food': 'food-apple-outline',
  'h-sleep': 'bed-outline', 'h-books': 'bookshelf', 'h-study': 'school-outline', 'h-lang': 'translate', 'h-write': 'pencil-outline',
  'h-speak': 'account-voice', 'h-work': 'briefcase-outline', 'h-clean': 'broom', 'h-money': 'cash', 'h-nophone': 'cellphone-off',
  'h-moon': 'moon-waning-crescent', 'h-sun': 'white-balance-sunny', 'h-sunrise': 'weather-sunset-up', 'h-sunset': 'weather-sunset-down',
  'h-target': 'target', 'h-timer': 'timer-outline', 'h-coffee': 'coffee-outline', 'h-leaf': 'leaf', 'h-bike': 'bike', 'h-apple': 'food-apple-outline',
  'h-idea': 'lightbulb-outline', 'h-list': 'format-list-checks', 'h-home': 'home-outline', 'h-family': 'account-group-outline',
  'h-heart': 'heart-outline', 'h-star': 'star-outline', 'h-together': 'handshake-outline', 'h-meet': 'calendar-month-outline',
};
export const ICONS = ['h-check', 'h-pill', 'h-water', 'h-quran', 'h-mosque', 'h-dua', 'h-run', 'h-walk', 'h-sport', 'h-mind', 'h-food', 'h-sleep',
  'h-books', 'h-study', 'h-lang', 'h-write', 'h-speak', 'h-work', 'h-clean', 'h-money', 'h-nophone', 'h-moon', 'h-sun', 'h-sunrise',
  'h-target', 'h-timer', 'h-coffee', 'h-leaf', 'h-bike', 'h-apple', 'h-idea', 'h-list', 'h-home', 'h-family', 'h-heart', 'h-star'];

/** Значок привычки или общего трекера: ключ из набора → рисунок; старое значение-эмодзи показываем как есть. */
export function HabitIcon({ value, size = 22, color }: { value: string; size?: number; color?: string }) {
  const { c } = useApp();
  const name = HABIT_ICON[value];
  if (name) return <MaterialCommunityIcons name={name} size={size} color={color ?? c.accent} />;
  return <Txt style={{ fontSize: size, lineHeight: size * 1.2 }}>{value}</Txt>;
}
export const COLORS = ['#6d5efc', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#8b5cf6', '#14b8a6', '#64748b'];

/** Сегодняшняя дата телефона в виде ГГГГ-ММ-ДД (сервер считает «день» по присланному). */
export function isoDay(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function Ring({ percent, size = 68 }: { percent: number; size?: number }) {
  const { c } = useApp();
  const r = size / 2 - 5;
  const len = 2 * Math.PI * r;
  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={size} height={size} style={{ position: 'absolute', transform: [{ rotate: '-90deg' }] }}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={c.line} strokeWidth={7} fill="none" />
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={percent >= 100 ? c.ok : c.accent} strokeWidth={7} fill="none" strokeLinecap="round"
          strokeDasharray={`${len}`} strokeDashoffset={len * (1 - Math.min(100, percent) / 100)} />
      </Svg>
      <Txt style={{ fontWeight: '800', fontSize: size * 0.22 }}>{percent}%</Txt>
    </View>
  );
}

export function HabitRow({ h, canMark, onToggle, onStep, onEdit, onMore, hideBoard }: {
  h: Habit; canMark: boolean; onToggle: (h: Habit) => void; onStep: (h: Habit, by: number) => void; onEdit?: (h: Habit) => void;
  onMore?: (h: Habit) => void; hideBoard?: boolean;
}) {
  const { c, t, dark } = useApp();
  const parts: { text: string; icon?: 'flame' | 'alarm-outline' }[] = [
    h.kind === 'count' ? { text: `${h.value} / ${h.target} ${h.unit}`.trim() } : null,
    h.streak ? { icon: 'flame' as const, text: h.per_week ? t('{n} нед. подряд', { n: h.streak }) : t('{n} дн. подряд', { n: h.streak }) } : null,
    h.per_week ? { text: t('{a}/{b} на неделе', { a: h.week_done ?? 0, b: h.per_week }) } : null,
    h.board_title && !hideBoard ? { text: h.board_title } : null,
    h.once_on ? { text: t('разовое дело') } : null,
    h.skipped ? { text: t('пропуск') } : null,
    h.reminders?.length ? { icon: 'alarm-outline' as const, text: h.reminders.join(', ') } : null,
  ].filter((x): x is { text: string; icon?: 'flame' | 'alarm-outline' } => !!x);
  const press = (fn: () => void) => () => { Haptics.selectionAsync().catch(() => {}); fn(); };
  return (
    <Pressable onPress={onMore ? () => onMore(h) : undefined} onLongPress={onMore ? () => onMore(h) : onEdit && h.can_edit ? () => onEdit(h) : undefined} delayLongPress={350}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: c.card, borderRadius: 18, paddingVertical: 11, paddingRight: 12, paddingLeft: 12,
        borderLeftWidth: 4, borderLeftColor: h.color, opacity: h.skipped ? 0.6 : 1, ...(dark ? {} : { shadowColor: '#15172a', shadowOpacity: 0.05, shadowRadius: 8, shadowOffset: { width: 0, height: 2 }, elevation: 1 }) }}>
      <View style={{ width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: h.skipped ? c.card2 : h.color + '24' }}>
        <HabitIcon value={h.emoji} size={21} color={h.skipped ? c.inkSoft : h.color} />
      </View>
      <View style={{ flex: 1 }}>
        <Txt style={{ fontSize: 16, fontWeight: '700', textDecorationLine: h.done ? 'line-through' : 'none' }} color={h.done ? c.inkSoft : c.ink}>{h.title}</Txt>
        {parts.length ? (
          <Txt kind="small" style={{ fontSize: 12.5 }}>
            {parts.map((x, i) => (
              <Txt key={i} kind="small" style={{ fontSize: 12.5 }}>{i ? ' · ' : ''}{x.icon ? <Icon name={x.icon} size={12.5} color={x.icon === 'flame' ? '#f97316' : c.inkSoft} /> : null}{x.icon ? ' ' : ''}{x.text}</Txt>
            ))}
          </Txt>
        ) : null}
        {h.note ? <Txt kind="small" style={{ fontSize: 12.5 }} numberOfLines={1}>{h.note}</Txt> : null}
        {h.log_note ? <Txt kind="small" color={c.accentD} style={{ fontSize: 12.5 }} numberOfLines={2}><Icon name="create-outline" size={12.5} color={c.accentD} /> {h.log_note}</Txt> : null}
        {h.who ? (
          <View style={{ flexDirection: 'row', gap: 4, marginTop: 5, flexWrap: 'wrap' }}>
            {h.who.map((p) => (
              <View key={p.id} style={{ width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: p.done ? h.color : c.card2, borderWidth: 1.5, borderColor: p.done ? h.color : c.line }}>
                <Txt style={{ fontSize: 11, lineHeight: 14, fontWeight: '800' }} color={p.done ? '#fff' : c.inkSoft}>{p.name.slice(0, 1).toUpperCase()}</Txt>
              </View>
            ))}
          </View>
        ) : null}
      </View>
      {onEdit && h.can_edit ? <Pressable onPress={() => onEdit(h)} hitSlop={8} style={{ padding: 4, opacity: 0.5 }} accessibilityLabel={t('Изменить')}><Icon name="create-outline" size={17} color={c.inkSoft} /></Pressable> : null}
      {canMark && h.kind === 'count' ? (
        <Pressable onPress={press(() => onStep(h, -1))} hitSlop={6} style={{ width: 34, height: 34, borderRadius: 17, borderWidth: 2, borderColor: c.line, alignItems: 'center', justifyContent: 'center' }}>
          <Icon name="remove" size={18} color={c.inkSoft} />
        </Pressable>
      ) : null}
      {canMark ? (
        <Pressable onPress={press(() => (h.kind === 'count' ? onStep(h, 1) : onToggle(h)))} hitSlop={6} accessibilityLabel={t('Отметить')}
          style={{ width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: h.color, backgroundColor: h.done ? h.color : 'transparent', alignItems: 'center', justifyContent: 'center' }}>
          <Icon name={h.kind === 'count' && !h.done ? 'add' : 'checkmark'} size={22} color={h.done ? '#fff' : h.color} style={{ opacity: h.done || h.kind === 'count' ? 1 : 0.4 }} />
        </Pressable>
      ) : null}
    </Pressable>
  );
}
