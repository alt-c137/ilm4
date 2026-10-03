/**
 * Сообщение в чате: «пузырь» в стиле современных мессенджеров.
 * - свои — справа, с градиентом; чужие — слева, на светлой карточке;
 * - подряд идущие сообщения одного человека слипаются в группу (маленькие углы, один «хвостик»);
 * - время и галочки — внутри пузыря, в правом нижнем углу (у фото и видео — поверх картинки);
 * - в группе: имя автора над первым сообщением и кружок-аватар у последнего.
 */
import * as Haptics from 'expo-haptics';
import { LinearGradient } from 'expo-linear-gradient';
import { memo } from 'react';
import { Pressable, Text, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { FadeIn, FadeInDown, FadeOut, interpolate, useAnimatedStyle, useSharedValue, withTiming, ZoomOut } from 'react-native-reanimated';

import { useApp } from '@/state/app';

import { Avatar, Icon } from './kit';
import { ChatFile, ChatPhoto, ChatVideo, ChatVoice } from './media';
import { Rich } from './rich';

export type Reply = { id: number; name: string; kind: string; text: string; hue: number };
export type Fwd = { name: string; user: number | null; room: number | null };
export type Rx = { e: string; n: number };
export type Msg = {
  id: number; sender_id: number; sender_name: string; kind: string; body: string; url: string; duration: number; time: string; day: string;
  mine?: boolean; read?: boolean; scheduled?: boolean; scheduled_label?: string; silent?: boolean;
  file_name?: string; file_size?: number; w?: number; h?: number; file_risky?: boolean; warn?: boolean; room?: string; views?: number; hue?: number;
  // как в Telegram: ответ, пересылка, правка, закреп, реакции, комментарии к посту
  reply?: Reply | null; fwd?: Fwd | null; edited?: boolean; pinned?: boolean; reactions?: Rx[]; my_reaction?: string;
  comment_of?: number | null; comments?: number; iso?: string; thread?: number;
};

const NAME_COLORS = ['#e8553d', '#d98a1b', '#665fff', '#3aa94f', '#17a595', '#2a8fdc', '#c453dd'];
const MONTHS: Record<string, string[]> = {
  ru: ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
  uz: ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'],
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
};

/** «Сегодня», «Вчера», «2 октября», «2 октября 2025» — из даты вида 2026-10-02. */
export function dayLabel(day: string, lang: string, t: (s: string) => string): string {
  const [y, m, d] = day.split('-').map(Number);
  const now = new Date();
  const that = new Date(y, m - 1, d);
  const diff = Math.round((new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() - that.getTime()) / 86400000);
  if (diff === 0) return t('Сегодня');
  if (diff === 1) return t('Вчера');
  const months = MONTHS[lang] ?? MONTHS.ru;
  const text = lang === 'en' ? `${months[m - 1]} ${d}` : lang === 'uz' ? `${d}-${months[m - 1]}` : `${d} ${months[m - 1]}`;
  return y === now.getFullYear() ? text : `${text} ${y}`;
}

export function DayPill({ text }: { text: string }) {
  const { dark } = useApp();
  return (
    <View style={{ alignSelf: 'center', marginTop: 12, marginBottom: 6, paddingHorizontal: 11, paddingVertical: 4, borderRadius: 12,
      backgroundColor: dark ? 'rgba(255,255,255,0.12)' : 'rgba(30,28,70,0.28)' }}>
      <Text style={{ color: '#fff', fontSize: 12.5, fontWeight: '600' }}>{text}</Text>
    </View>
  );
}

type Props = {
  m: Msg; first: boolean; last: boolean; group: boolean; animate: boolean;
  flash?: boolean; comments?: boolean; canReply?: boolean;
  onLongPress: (m: Msg) => void; onScheduled: (m: Msg, action: 'send' | 'cancel') => void;
  onReply?: (m: Msg) => void; onGoto?: (id: number) => void; onReact?: (m: Msg, emoji: string) => void;
  onPhoto?: (m: Msg) => void; onFwd?: (f: Fwd) => void; onComments?: (m: Msg) => void;
};

const SWIPE = -64;

export const Bubble = memo(function Bubble({ m, first, last, group, animate, flash, comments, canReply, onLongPress, onScheduled,
  onReply, onGoto, onReact, onPhoto, onFwd, onComments }: Props) {
  const { c, t, dark } = useApp();
  const mine = !!m.mine;
  const media = m.kind === 'photo' || m.kind === 'video';
  const circle = m.kind === 'circle';
  const fg = mine ? '#fff' : c.ink;
  const soft = mine ? 'rgba(255,255,255,0.78)' : c.inkSoft;
  const showName = group && !mine && first;
  const pad = media || circle ? 8 : 0;

  // свайп влево — ответить (как в Telegram)
  const tx = useSharedValue(0);
  const swipe = Gesture.Pan().enabled(!!onReply && !!canReply && !m.scheduled).activeOffsetX(-14).failOffsetY([-12, 12]).runOnJS(true)
    .onUpdate((e) => { tx.value = Math.max(SWIPE - 16, Math.min(0, e.translationX)); })
    .onEnd((e) => {
      if (e.translationX <= SWIPE) {
        Haptics.selectionAsync().catch(() => {});
        onReply?.(m);
      }
      tx.value = withTiming(0, { duration: 160 });
    });
  const moved = useAnimatedStyle(() => ({ transform: [{ translateX: tx.value }] }));
  const hint = useAnimatedStyle(() => ({ opacity: interpolate(tx.value, [SWIPE, -18, 0], [1, 0.2, 0]), transform: [{ scale: interpolate(tx.value, [SWIPE, 0], [1, 0.6]) }] }));

  // время, галочки, просмотры — одной строкой
  const meta = (color: string) => (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }}>
      {m.pinned ? <Icon name="pin" size={11} color={color} /> : null}
      {m.room === 'channel' ? <><Icon name="eye-outline" size={13} color={color} /><Text style={{ color, fontSize: 11 }}>{m.views ?? 0}</Text><View style={{ width: 3 }} /></> : null}
      {m.silent ? <Icon name="notifications-off-outline" size={11} color={color} /> : null}
      {m.edited ? <Text style={{ color, fontSize: 11 }}>{t('изменено')}</Text> : null}
      <Text style={{ color, fontSize: 11, fontVariant: ['tabular-nums'] }}>{m.time}</Text>
      {mine && m.room !== 'channel' ? <Icon name={m.read ? 'checkmark-done' : 'checkmark'} size={15} color={color} /> : null}
    </View>
  );
  // невидимый «хвост» в конце текста резервирует место под время и галочки — теми же знаками, тем же размером,
  // поэтому текст не наезжает на время (в Telegram так же: время стоит в конце последней строки)
  const tail = '\u00a0\u00a0' + (m.room === 'channel' ? `OO${m.views ?? 0}\u00a0` : '') + (m.pinned ? 'O\u00a0' : '') + (m.silent ? 'O\u00a0' : '')
    + (m.edited ? `${t('изменено')}\u00a0` : '') + m.time + (mine && m.room !== 'channel' ? '\u00a0OO' : '') + '\u00a0';

  const big = 20;
  const small = 7;
  const radius = {
    borderTopLeftRadius: mine || first ? big : small, borderTopRightRadius: !mine || first ? big : small,
    borderBottomLeftRadius: mine ? big : last ? 5 : small, borderBottomRightRadius: !mine ? big : last ? 5 : small,
  };
  const replyColor = mine ? '#fff' : NAME_COLORS[(m.reply?.hue ?? 0) % 7];
  const rx = m.reactions ?? [];
  const inner = (
    <>
      {showName ? (
        <Text style={{ color: NAME_COLORS[(m.hue ?? 0) % 7], fontWeight: '700', fontSize: 13, marginBottom: 2, paddingHorizontal: pad, paddingTop: media ? 4 : 0 }}
          numberOfLines={1}>{m.sender_name}</Text>
      ) : null}
      {m.fwd ? (
        <Pressable onPress={() => m.fwd && (m.fwd.user || m.fwd.room) && onFwd?.(m.fwd)} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 3, paddingHorizontal: pad, paddingTop: media ? 4 : 0 }}>
          <Icon name="arrow-redo-outline" size={13} color={mine ? '#fff' : c.accentD} />
          <Text style={{ color: mine ? '#fff' : c.accentD, fontSize: 13, fontWeight: '600', flexShrink: 1 }} numberOfLines={1}>
            {t('Переслано от')} <Text style={{ fontWeight: '800' }}>{m.fwd.name}</Text></Text>
        </Pressable>
      ) : null}
      {m.reply ? (
        <Pressable onPress={() => m.reply && onGoto?.(m.reply.id)}
          style={{ borderLeftWidth: 3, borderLeftColor: replyColor, borderRadius: 7, paddingVertical: 4, paddingHorizontal: 9, marginBottom: 5, marginHorizontal: media || circle ? 5 : 0,
            marginTop: media ? 4 : 1, minWidth: 140, backgroundColor: mine ? 'rgba(255,255,255,0.18)' : `${replyColor}1f` }}>
          <Text style={{ color: replyColor, fontSize: 13, fontWeight: '800' }} numberOfLines={1}>{m.reply.name}</Text>
          <Text style={{ color: fg, opacity: 0.85, fontSize: 13.5 }} numberOfLines={1}>{m.reply.text}</Text>
        </Pressable>
      ) : null}
      {m.kind === 'photo' ? <ChatPhoto uri={m.url} w={m.w} h={m.h} onPress={onPhoto ? () => onPhoto(m) : undefined} /> : null}
      {m.kind === 'video' ? <ChatVideo uri={m.url} /> : null}
      {circle ? <ChatVideo uri={m.url} round /> : null}
      {m.kind === 'voice' ? <ChatVoice uri={m.url} duration={m.duration} mine={mine} /> : null}
      {m.kind === 'file' ? <ChatFile uri={m.url} name={m.file_name ?? ''} size={m.file_size ?? 0} mine={mine} /> : null}
      {m.kind === 'file' && m.file_risky && !mine ? (
        <View style={{ flexDirection: 'row', gap: 6, backgroundColor: '#fff4d6', borderRadius: 10, padding: 8, marginTop: 4 }}>
          <Icon name="shield-outline" size={15} color="#7a5600" />
          <Text style={{ flex: 1, color: '#7a5600', fontSize: 12.5 }}>{t('Это программа. Открывайте, только если доверяете отправителю.')}</Text>
        </View>
      ) : null}
      {m.body && m.kind !== 'voice' ? (
        <Text selectable style={{ color: fg, fontSize: 16, lineHeight: 22, paddingHorizontal: pad, paddingTop: media ? 6 : 0, paddingBottom: media ? 4 : 0 }}>
          <Rich text={m.body} color={fg} />{!m.scheduled ? <Text style={{ fontSize: 11.5, color: 'transparent' }}>{tail}</Text> : null}
        </Text>
      ) : null}
      {m.scheduled ? (
        <View style={{ gap: 7, paddingTop: 4, paddingHorizontal: pad, paddingBottom: media ? 6 : 0 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
            <Icon name="time-outline" size={14} color="#fff" />
            <Text style={{ color: '#fff', fontSize: 12.5, fontWeight: '700' }}>{m.scheduled_label}</Text>
          </View>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {(['send', 'cancel'] as const).map((a) => (
              <Pressable key={a} onPress={() => onScheduled(m, a)} style={{ backgroundColor: 'rgba(255,255,255,0.22)', borderRadius: 999, paddingHorizontal: 11, paddingVertical: 5 }}>
                <Text style={{ color: '#fff', fontSize: 12.5, fontWeight: '600' }}>{a === 'send' ? t('Отправить сейчас') : t('Удалить')}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ) : m.body && m.kind !== 'voice' ? (
        <View style={{ position: 'absolute', right: media ? 10 : 12, bottom: (media ? 8 : 7) + (rx.length ? 33 : 0) + (comments ? 41 : 0) }}>{meta(soft)}</View>
      ) : (media || circle) && !rx.length && !comments ? (
        // у фото и видео без подписи время лежит поверх картинки
        <View style={{ position: 'absolute', right: 9, bottom: 9, backgroundColor: 'rgba(0,0,0,0.45)', borderRadius: 10, paddingHorizontal: 7, paddingVertical: 2 }}>{meta('#fff')}</View>
      ) : (
        <View style={{ alignSelf: 'flex-end', marginTop: 2, paddingHorizontal: pad }}>{meta(soft)}</View>
      )}
      {rx.length ? (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 6, paddingHorizontal: pad, paddingBottom: media ? 4 : 0 }}>
          {rx.map((r) => {
            const on = r.e === m.my_reaction;
            return (
              <Pressable key={r.e} onPress={() => onReact?.(m, r.e)} hitSlop={4}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 4, height: 27, paddingLeft: 7, paddingRight: 9, borderRadius: 14,
                  backgroundColor: mine ? (on ? '#fff' : 'rgba(255,255,255,0.2)') : on ? c.accent : c.accentSoft }}>
                <Text style={{ fontSize: 15 }}>{r.e}</Text>
                <Text style={{ fontSize: 12.5, fontWeight: '800', color: mine ? (on ? c.accentD : '#fff') : on ? '#fff' : c.accentD }}>{r.n}</Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}
      {comments && !m.scheduled ? (
        <Pressable onPress={() => onComments?.(m)}
          style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 7, marginHorizontal: media ? 0 : -12, marginBottom: media ? 0 : -7, paddingHorizontal: 12, paddingVertical: 9,
            borderTopWidth: 0.5, borderTopColor: mine ? 'rgba(255,255,255,0.3)' : c.line }}>
          <Icon name="chatbubble-outline" size={16} color={mine ? '#fff' : c.accentD} />
          <Text style={{ flex: 1, color: mine ? '#fff' : c.accentD, fontSize: 14, fontWeight: '700' }}>
            {m.comments ? `${t('Комментарии')} · ${m.comments}` : t('Комментировать')}</Text>
          <Icon name="chevron-forward" size={16} color={mine ? '#fff' : c.accentD} />
        </Pressable>
      ) : null}
    </>
  );
  const box = [{
    maxWidth: '100%' as const, overflow: 'hidden' as const, ...radius,
    paddingHorizontal: media || circle ? 3 : 12, paddingVertical: media || circle ? 3 : 7,
    opacity: m.scheduled ? 0.9 : 1,
  }, m.scheduled && { borderWidth: 1.5, borderStyle: 'dashed' as const, borderColor: 'rgba(255,255,255,0.75)' }];

  return (
    <View style={{ marginTop: first ? 8 : 2 }}>
      {flash ? (
        // переход к сообщению (ответ, закреп, поиск): строка подсвечивается и гаснет
        <Animated.View entering={FadeIn.duration(160)} exiting={FadeOut.duration(500)} pointerEvents="none"
          style={{ position: 'absolute', left: -10, right: -10, top: -2, bottom: -2, backgroundColor: c.accent, opacity: 0.16 }} />
      ) : null}
      <Animated.View pointerEvents="none" style={[{ position: 'absolute', right: 4, top: 0, bottom: 0, justifyContent: 'center' }, hint]}>
        <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
          <Icon name="arrow-undo" size={17} color={c.accent} />
        </View>
      </Animated.View>
      <GestureDetector gesture={swipe}>
        <Animated.View style={[{ flexDirection: 'row', alignItems: 'flex-end', justifyContent: mine ? 'flex-end' : 'flex-start', gap: 6 }, moved]}>
          {group && !mine ? (last ? <Avatar name={m.sender_name} size={30} hue={m.hue ?? 0} /> : <View style={{ width: 30 }} />) : null}
          <Pressable onLongPress={() => onLongPress(m)} delayLongPress={380} style={{ maxWidth: group && !mine ? '80%' : '82%' }}>
            <Animated.View entering={animate ? FadeInDown.duration(180) : undefined} exiting={m.scheduled ? ZoomOut.duration(160) : undefined}
              style={!mine && !dark && !circle ? { shadowColor: '#1b1a4a', shadowOpacity: 0.07, shadowRadius: 5, shadowOffset: { width: 0, height: 1 }, elevation: 1, ...radius } : undefined}>
              {circle ? <View style={box}>{inner}</View>
                : mine ? <LinearGradient colors={dark ? ['#7265f2', '#5547d8'] : ['#7c6dff', '#5d4fe9']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={box}>{inner}</LinearGradient>
                  : <View style={[box, { backgroundColor: c.card }]}>{inner}</View>}
            </Animated.View>
          </Pressable>
        </Animated.View>
      </GestureDetector>
    </View>
  );
});
