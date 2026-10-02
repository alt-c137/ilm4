/**
 * Редактор фото перед отправкой, как в Telegram: рисовать пальцем, подписать текстом, отменить шаг.
 * Результат — снимок области с фото (react-native-view-shot); ничего не меняли — уходит исходный файл.
 */
/* eslint-disable react-hooks/refs -- обработчики касаний (PanResponder) читают ref по касанию, а не во время отрисовки */
import { Image } from 'expo-image';
import { useMemo, useRef, useState } from 'react';
import { Modal, PanResponder, Pressable, Text, TextInput, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { captureRef } from 'react-native-view-shot';

import { useApp } from '@/state/app';

import { Icon } from './kit';

export type EditPhoto = { uri: string; width: number; height: number };
type Stroke = { kind: 'pen'; d: string; color: string } | { kind: 'text'; text: string; x: number; y: number; color: string };
const COLORS = ['#ffffff', '#111827', '#ef4444', '#f59e0b', '#22c55e', '#3b82f6', '#a855f7'];

export function PhotoEditor({ photo, onDone }: { photo: EditPhoto | null; onDone: (uri: string | null) => void }) {
  const { c, t } = useApp();
  const win = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const stage = useRef<View>(null);
  const [ops, setOps] = useState<Stroke[]>([]);
  const [color, setColor] = useState(COLORS[2]);
  const [typing, setTyping] = useState<string | null>(null);     // текст, который ждёт места на фото
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const live = useRef<{ d: string } | null>(null);
  const colorRef = useRef(color);
  colorRef.current = color;
  const typingRef = useRef(typing);
  typingRef.current = typing;

  const maxW = win.width - 16;
  const maxH = win.height - insets.top - insets.bottom - 210;
  const ratio = photo ? photo.width / Math.max(1, photo.height) : 1;
  const w = Math.min(maxW, maxH * ratio);
  const h = w / ratio;

  const pan = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: (e) => {
      const { locationX: x, locationY: y } = e.nativeEvent;
      if (typingRef.current) {
        const text = typingRef.current;
        setOps((old) => [...old, { kind: 'text', text, x, y, color: colorRef.current }]);
        setTyping(null);
        return;
      }
      live.current = { d: `M${x.toFixed(1)} ${y.toFixed(1)}` };
      setOps((old) => [...old, { kind: 'pen', d: `${live.current!.d} l0.1 0`, color: colorRef.current }]);
    },
    onPanResponderMove: (e) => {
      if (!live.current) return;
      const { locationX: x, locationY: y } = e.nativeEvent;
      live.current.d += ` L${x.toFixed(1)} ${y.toFixed(1)}`;
      const d = live.current.d;
      setOps((old) => (old.length ? [...old.slice(0, -1), { ...(old[old.length - 1] as any), d }] : old));
    },
    onPanResponderRelease: () => { live.current = null; },
    onPanResponderTerminate: () => { live.current = null; },
  }), []);

  if (!photo) return null;
  const close = (uri: string | null) => { setOps([]); setTyping(null); setDraft(''); onDone(uri); };
  const send = async () => {
    if (!ops.length) return close(photo.uri);
    setBusy(true);
    try {
      close(await captureRef(stage, { format: 'jpg', quality: 0.92, result: 'tmpfile' }));
    } catch {
      close(photo.uri);
    } finally {
      setBusy(false);
    }
  };
  const round = { width: 42, height: 42, borderRadius: 21, backgroundColor: 'rgba(255,255,255,0.14)', alignItems: 'center' as const, justifyContent: 'center' as const };

  return (
    <Modal visible animationType="fade" onRequestClose={() => close(null)} statusBarTranslucent>
      <View style={{ flex: 1, backgroundColor: '#0b0d16', paddingTop: insets.top + 8, paddingBottom: insets.bottom + 12, paddingHorizontal: 8, gap: 10 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Pressable onPress={() => close(null)} style={round} accessibilityLabel={t('Отмена')}><Icon name="close" size={22} color="#fff" /></Pressable>
          <Pressable onPress={() => setOps((old) => old.slice(0, -1))} disabled={!ops.length} style={[round, { opacity: ops.length ? 1 : 0.4 }]} accessibilityLabel={t('Отменить шаг')}>
            <Icon name="arrow-undo" size={20} color="#fff" />
          </Pressable>
          <View style={{ flex: 1 }} />
          <Pressable onPress={() => { setDraft(''); setTyping(''); }} style={[round, { width: undefined, paddingHorizontal: 16, backgroundColor: typing !== null ? '#fff' : 'rgba(255,255,255,0.14)' }]}>
            <Text style={{ color: typing !== null ? '#111' : '#fff', fontWeight: '700' }}>Аа {t('Текст')}</Text>
          </Pressable>
        </View>
        {typing === '' ? (
          <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
            <TextInput value={draft} onChangeText={setDraft} autoFocus maxLength={80} placeholder={t('Напишите текст')} placeholderTextColor="rgba(255,255,255,0.5)"
              onSubmitEditing={() => setTyping(draft.trim() || null)} returnKeyType="done"
              style={{ flex: 1, height: 44, borderRadius: 14, paddingHorizontal: 14, backgroundColor: 'rgba(255,255,255,0.14)', color: '#fff', fontSize: 16 }} />
            <Pressable onPress={() => setTyping(draft.trim() || null)} style={[round, { backgroundColor: c.accent }]}><Icon name="checkmark" size={22} color="#fff" /></Pressable>
          </View>
        ) : typing ? <Text style={{ color: 'rgba(255,255,255,0.8)', textAlign: 'center' }}>{t('Нажмите на фото — туда встанет текст')}</Text> : null}
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <View ref={stage} collapsable={false} style={{ width: w, height: h, borderRadius: 8, overflow: 'hidden', backgroundColor: '#000' }} {...pan.panHandlers}>
            <Image source={{ uri: photo.uri }} style={{ width: w, height: h }} contentFit="cover" />
            <Svg width={w} height={h} style={{ position: 'absolute' }} pointerEvents="none">
              {ops.map((o, i) => (o.kind === 'pen' ? <Path key={i} d={o.d} stroke={o.color} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" fill="none" /> : null))}
            </Svg>
            {ops.map((o, i) => (o.kind === 'text' ? (
              <Text key={i} pointerEvents="none" style={{ position: 'absolute', left: 0, right: 0, top: o.y - 18, textAlign: 'center', transform: [{ translateX: o.x - w / 2 }],
                color: o.color, fontSize: 26, fontWeight: '800', textShadowColor: o.color === '#111827' ? '#fff' : 'rgba(0,0,0,0.75)', textShadowRadius: 5, textShadowOffset: { width: 0, height: 1 } }}>{o.text}</Text>
            ) : null))}
          </View>
        </View>
        <View style={{ flexDirection: 'row', gap: 9, justifyContent: 'center' }}>
          {COLORS.map((col) => (
            <Pressable key={col} onPress={() => setColor(col)} style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: col, borderWidth: color === col ? 3 : 1.5,
              borderColor: color === col ? '#fff' : 'rgba(255,255,255,0.35)', transform: [{ scale: color === col ? 1.15 : 1 }] }} />
          ))}
        </View>
        <Pressable onPress={send} disabled={busy} style={{ height: 50, borderRadius: 16, backgroundColor: c.accent, alignItems: 'center', justifyContent: 'center', opacity: busy ? 0.6 : 1 }}>
          <Text style={{ color: '#fff', fontSize: 16, fontWeight: '800' }}>{t('Отправить')}</Text>
        </Pressable>
      </View>
    </Modal>
  );
}
