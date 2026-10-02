/** Трекер привычек: общие части экранов — строка привычки с отметкой и кольцо выполнения. */
import * as Haptics from 'expo-haptics';
import { Pressable, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

import { useApp } from '@/state/app';

import { Icon, Txt } from './kit';

export type Habit = {
  id: number; title: string; emoji: string; color: string; kind: 'check' | 'count'; target: number; unit: string; days: string;
  once_on: string; remind_at: string; board: number | null; board_title: string; value: number; done: boolean; due: boolean;
  streak: number; best: number; can_edit: boolean; archived: boolean; who?: { id: number; name: string; done: boolean }[];
};
export const EMOJI = ['✅', '💊', '💧', '📖', '🕌', '🤲', '🏃', '🧘', '🥗', '😴', '📚', '✍️', '🗣', '💼', '🧹', '💰', '📵', '🌙', '☀️', '🎯'];
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

export function HabitRow({ h, canMark, onToggle, onStep, onEdit, hideBoard }: {
  h: Habit; canMark: boolean; onToggle: (h: Habit) => void; onStep: (h: Habit, by: number) => void; onEdit?: (h: Habit) => void; hideBoard?: boolean;
}) {
  const { c, t, dark } = useApp();
  const parts = [
    h.kind === 'count' ? `${h.value} / ${h.target} ${h.unit}`.trim() : '',
    h.streak ? t('🔥 {n} дн. подряд', { n: h.streak }) : '',
    h.board_title && !hideBoard ? h.board_title : '',
    h.once_on ? t('разовое дело') : '',
  ].filter(Boolean);
  const press = (fn: () => void) => () => { Haptics.selectionAsync().catch(() => {}); fn(); };
  return (
    <Pressable onLongPress={onEdit && h.can_edit ? () => onEdit(h) : undefined} delayLongPress={350}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: c.card, borderRadius: 18, paddingVertical: 11, paddingRight: 12, paddingLeft: 12,
        borderLeftWidth: 4, borderLeftColor: h.color, ...(dark ? {} : { shadowColor: '#15172a', shadowOpacity: 0.05, shadowRadius: 8, shadowOffset: { width: 0, height: 2 }, elevation: 1 }) }}>
      <Txt style={{ fontSize: 25, lineHeight: 30, width: 32, textAlign: 'center' }}>{h.emoji}</Txt>
      <View style={{ flex: 1 }}>
        <Txt style={{ fontSize: 16, fontWeight: '700', textDecorationLine: h.done ? 'line-through' : 'none' }} color={h.done ? c.inkSoft : c.ink}>{h.title}</Txt>
        {parts.length ? <Txt kind="small" style={{ fontSize: 12.5 }}>{parts.join(' · ')}</Txt> : null}
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
