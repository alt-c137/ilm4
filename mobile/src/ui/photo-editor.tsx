/**
 * Редактор фото — по образцу Telegram: кадр (рамка, пропорции, поворот, отражение), цвет (яркость, контраст,
 * насыщенность, теплота, выцветание, виньетка), рисунок (карандаш, маркер, стрелка), текст.
 * Тот же набор и те же формулы цвета, что на сайте (static/js/photoedit.js).
 *
 * Всё рисуется одним SVG в единицах фото; результат — снимок этой области (react-native-view-shot).
 * Ничего не меняли — уходит исходный файл. Режим avatar — квадрат с кругом-подсказкой, на выходе 640×640.
 */
/* eslint-disable react-hooks/refs -- обработчики касаний (PanResponder) читают ref по касанию, а не во время отрисовки */
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { FlipType, manipulateAsync, SaveFormat, type Action } from 'expo-image-manipulator';
import * as ImagePicker from 'expo-image-picker';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Modal, PanResponder, Pressable, ScrollView, Text, TextInput, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Defs, FeColorMatrix, Filter, G, Image as SvgImage, Line, Path, Polygon, RadialGradient, Rect, Stop, Text as SvgText } from 'react-native-svg';
import { captureRef } from 'react-native-view-shot';

import { useApp } from '@/state/app';

export type EditPhoto = { uri: string; width: number; height: number };
type Pt = [number, number];
type Op = { kind: 'pen'; pts: Pt[]; color: string; w: number; marker: boolean } | { kind: 'arrow'; a: Pt; b: Pt; color: string; w: number }
  | { kind: 'text'; text: string; x: number; y: number; color: string; size: number };
type Rect4 = { x: number; y: number; w: number; h: number };
type Mode = 'crop' | 'adjust' | 'draw' | 'text';
type Adj = { b: number; c: number; s: number; w: number; f: number; v: number };
type MCI = keyof typeof MaterialCommunityIcons.glyphMap;

const COLORS = ['#ffffff', '#111827', '#ef4444', '#f59e0b', '#22c55e', '#3b82f6', '#a855f7'];
const ZERO: Adj = { b: 0, c: 0, s: 0, w: 0, f: 0, v: 0 };
const PARAMS: { key: keyof Adj; label: string; icon: MCI; min: number }[] = [
  { key: 'b', label: 'Яркость', icon: 'brightness-6', min: -1 }, { key: 'c', label: 'Контраст', icon: 'contrast-circle', min: -1 },
  { key: 's', label: 'Насыщенность', icon: 'water-outline', min: -1 }, { key: 'w', label: 'Теплота', icon: 'thermometer', min: -1 },
  { key: 'f', label: 'Выцветание', icon: 'blur', min: 0 }, { key: 'v', label: 'Виньетка', icon: 'image-filter-center-focus', min: 0 }];
const ASPECTS: { key: number; label: string }[] = [{ key: 0, label: 'Свободно' }, { key: -1, label: 'Оригинал' }, { key: 1, label: '1:1' },
  { key: 4 / 3, label: '4:3' }, { key: 3 / 4, label: '3:4' }, { key: 16 / 9, label: '16:9' }];
const MAX = 2048;

/** Матрица цвета для SVG-фильтра — те же формулы, что в редакторе сайта (значения каналов 0…1). */
function matrix(a: Adj): string | null {
  if (!a.b && !a.c && !a.s && !a.w && !a.f) return null;
  const B = (a.b * 70) / 255, C = a.c >= 0 ? 1 + a.c * 0.9 : 1 + a.c * 0.6, S = 1 + a.s, W = (a.w * 28) / 255, F = Math.max(0, a.f);
  const o = C * B + 0.5 - 0.5 * C, k = (1 - F * 0.32) * C, fa = (F * 46) / 255, q = 1 - F * 0.32;
  const lr = 0.299, lg = 0.587, lb = 0.114;
  const rows = [
    [k * (lr * (1 - S) + S), k * lg * (1 - S), k * lb * (1 - S), 0, q * (o + W) + fa],
    [k * lr * (1 - S), k * (lg * (1 - S) + S), k * lb * (1 - S), 0, q * o + fa],
    [k * lr * (1 - S), k * lg * (1 - S), k * (lb * (1 - S) + S), 0, q * (o - W) + fa],
    [0, 0, 0, 1, 0]];
  return rows.map((r) => r.map((v) => v.toFixed(4)).join(' ')).join(' ');
}

function Slider({ value, min, onChange }: { value: number; min: number; onChange: (v: number) => void }) {
  const width = useRef(1);
  const cb = useRef(onChange);
  cb.current = onChange;
  const range = useRef(min);
  range.current = min;
  const pan = useMemo(() => {
    const set = (x: number) => {
      const k = Math.max(0, Math.min(1, x / width.current));
      cb.current(Math.round((range.current + k * (1 - range.current)) * 100) / 100);
    };
    return PanResponder.create({
      onStartShouldSetPanResponder: () => true, onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (e) => set(e.nativeEvent.locationX), onPanResponderMove: (e) => set(e.nativeEvent.locationX),
    });
  }, []);
  const k = (value - min) / (1 - min);
  return (
    <View onLayout={(e) => { width.current = e.nativeEvent.layout.width; }} style={{ flex: 1, height: 36, justifyContent: 'center' }} {...pan.panHandlers}>
      <View pointerEvents="none" style={{ height: 4, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.22)' }}>
        <View style={{ width: `${k * 100}%` as `${number}%`, height: 4, borderRadius: 2, backgroundColor: '#fff' }} />
      </View>
      <View pointerEvents="none" style={{ position: 'absolute', left: `${k * 100}%` as `${number}%`, marginLeft: -11, width: 22, height: 22, borderRadius: 11, backgroundColor: '#fff' }} />
    </View>
  );
}

export function PhotoEditor({ photo, onDone, avatar, doneLabel }: {
  photo: EditPhoto | null; onDone: (uri: string | null) => void; avatar?: boolean; doneLabel?: string;
}) {
  const { c, t } = useApp();
  const win = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const stage = useRef<View>(null);
  const [base, setBase] = useState<EditPhoto | null>(null);          // фото после подготовки: ориентация применена, не больше 2048
  const [rot, setRot] = useState(0);
  const [flip, setFlip] = useState(false);
  const [crop, setCrop] = useState<Rect4>({ x: 0, y: 0, w: 1, h: 1 });
  const [aspect, setAspect] = useState(0);                           // пропорции рамки; 0 — свободно
  const [aspectKey, setAspectKey] = useState(0);
  const [adj, setAdj] = useState<Adj>(ZERO);
  const [param, setParam] = useState<keyof Adj>('b');
  const [ops, setOps] = useState<Op[]>([]);
  const [mode, setMode] = useState<Mode>(avatar ? 'crop' : 'draw');
  const [tool, setTool] = useState<'pen' | 'marker' | 'arrow'>('pen');
  const [color, setColor] = useState(COLORS[2]);
  const [size, setSize] = useState(2);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [shooting, setShooting] = useState(false);                   // идёт снимок результата: рамку не рисуем

  const uri = photo?.uri;
  useEffect(() => {
    if (!photo) return;
    let alive = true;
    const big = Math.max(photo.width, photo.height);
    manipulateAsync(photo.uri, big > MAX ? [{ resize: photo.width >= photo.height ? { width: MAX } : { height: MAX } }] : [], { compress: 0.95, format: SaveFormat.JPEG })
      .then((r) => ({ uri: r.uri, width: r.width, height: r.height }))
      .catch(() => photo)                                            // не вышло подготовить — работаем с исходным
      .then((b) => {
        if (!alive) return;
        setBase(b); setRot(0); setFlip(false); setAdj(ZERO); setOps([]); setDraft(''); setMode(avatar ? 'crop' : 'draw');
        const side = Math.min(b.width, b.height);
        setAspect(avatar ? 1 : 0); setAspectKey(avatar ? 1 : 0);
        setCrop(avatar ? { x: (b.width - side) / 2, y: (b.height - side) / 2, w: side, h: side } : { x: 0, y: 0, w: b.width, h: b.height });
      });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- новое фото = новый uri
  }, [uri, avatar]);

  const W = base?.width ?? 1, H = base?.height ?? 1;
  const dw = rot % 2 ? H : W, dh = rot % 2 ? W : H;                  // размеры фото после поворота
  const region: Rect4 = mode === 'crop' && !shooting ? { x: 0, y: 0, w: dw, h: dh } : crop;
  const maxW = win.width - 16, maxH = Math.max(160, win.height - insets.top - insets.bottom - 300);
  const scale = Math.min(maxW / region.w, maxH / region.h);
  const sw = region.w * scale, sh = region.h * scale;

  // обработчики касаний читают свежие значения отсюда
  const live = useRef({ mode, crop, region, scale, dw, dh, aspect, tool, color, size, ops });
  live.current = { mode, crop, region, scale, dw, dh, aspect, tool, color, size, ops };
  const drag = useRef<{ corner?: number; fx?: number; fy?: number; move?: Pt; draw?: boolean; text?: number; off?: Pt } | null>(null);

  const pan = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: (e) => {
      const s = live.current, p: Pt = [s.region.x + e.nativeEvent.locationX / s.scale, s.region.y + e.nativeEvent.locationY / s.scale];
      drag.current = null;
      if (s.mode === 'crop') {
        const k = s.crop, tol = 34 / s.scale;
        const corners: Pt[] = [[k.x, k.y], [k.x + k.w, k.y], [k.x, k.y + k.h], [k.x + k.w, k.y + k.h]];
        const hit = corners.findIndex((q) => Math.abs(p[0] - q[0]) < tol && Math.abs(p[1] - q[1]) < tol);
        if (hit >= 0) drag.current = { corner: hit, fx: corners[3 - hit][0], fy: corners[3 - hit][1] };
        else if (p[0] > k.x && p[0] < k.x + k.w && p[1] > k.y && p[1] < k.y + k.h) drag.current = { move: [p[0] - k.x, p[1] - k.y] };
      } else if (s.mode === 'draw') {
        const w = Math.max(2.5, s.dw / 300) * s.size * (s.tool === 'marker' ? 3 : 1);
        drag.current = { draw: true };
        setOps((old) => [...old, s.tool === 'arrow' ? { kind: 'arrow', a: p, b: p, color: s.color, w } : { kind: 'pen', pts: [p], color: s.color, w, marker: s.tool === 'marker' }]);
      } else if (s.mode === 'text') {
        for (let i = s.ops.length - 1; i >= 0; i--) {
          const o = s.ops[i];
          if (o.kind === 'text' && Math.abs(p[0] - o.x) < o.text.length * o.size * 0.33 + o.size * 0.4 && Math.abs(p[1] - o.y) < o.size) {
            drag.current = { text: i, off: [p[0] - o.x, p[1] - o.y] };
            break;
          }
        }
      }
    },
    onPanResponderMove: (e) => {
      const d = drag.current, s = live.current;
      if (!d) return;
      const p: Pt = [s.region.x + e.nativeEvent.locationX / s.scale, s.region.y + e.nativeEvent.locationY / s.scale];
      if (d.move) {
        const [ox, oy] = d.move;
        setCrop((k) => ({ ...k, x: Math.max(0, Math.min(s.dw - k.w, p[0] - ox)), y: Math.max(0, Math.min(s.dh - k.h, p[1] - oy)) }));
      } else if (d.corner !== undefined) {
        const fx = d.fx ?? 0, fy = d.fy ?? 0, min = Math.min(s.dw, s.dh) * 0.12;
        const px = Math.max(0, Math.min(s.dw, p[0])), py = Math.max(0, Math.min(s.dh, p[1]));
        const sx = d.corner % 2 ? 1 : -1, sy = d.corner > 1 ? 1 : -1;
        let w = Math.max(min, Math.abs(px - fx)), h = Math.max(min, Math.abs(py - fy));
        if (s.aspect > 0) {
          h = w / s.aspect;
          const mw = sx > 0 ? s.dw - fx : fx, mh = sy > 0 ? s.dh - fy : fy;
          if (w > mw) { w = mw; h = w / s.aspect; }
          if (h > mh) { h = mh; w = h * s.aspect; }
        }
        setCrop({ x: sx > 0 ? fx : fx - w, y: sy > 0 ? fy : fy - h, w, h });
      } else if (d.draw) {
        setOps((old) => {
          const last = old[old.length - 1];
          if (!last) return old;
          if (last.kind === 'arrow') return [...old.slice(0, -1), { ...last, b: p }];
          if (last.kind === 'pen') return [...old.slice(0, -1), { ...last, pts: [...last.pts, p] }];
          return old;
        });
      } else if (d.text !== undefined && d.off) {
        const i = d.text, [ox, oy] = d.off;
        setOps((old) => old.map((o, n) => (n === i && o.kind === 'text' ? { ...o, x: p[0] - ox, y: p[1] - oy } : o)));
      }
    },
    onPanResponderRelease: () => { drag.current = null; },
    onPanResponderTerminate: () => { drag.current = null; },
  }), []);

  if (!photo) return null;

  const fit = (a: number, around: Rect4 | null, w0: number, h0: number): Rect4 => {
    let w = w0, h = h0;
    if (a > 0) { if (w / h > a) w = h * a; else h = w / a; }
    const cx = around ? around.x + around.w / 2 : w0 / 2, cy = around ? around.y + around.h / 2 : h0 / 2;
    return { x: Math.max(0, Math.min(w0 - w, cx - w / 2)), y: Math.max(0, Math.min(h0 - h, cy - h / 2)), w, h };
  };
  // поворот и отражение переносят рамку и рисунки вместе с фото
  const rotate = () => {
    setOps((old) => old.map((o): Op => (o.kind === 'text' ? { ...o, x: dh - o.y, y: o.x } : o.kind === 'arrow'
      ? { ...o, a: [dh - o.a[1], o.a[0]], b: [dh - o.b[1], o.b[0]] } : { ...o, pts: o.pts.map((p): Pt => [dh - p[1], p[0]]) })));
    setCrop((k) => ({ x: dh - (k.y + k.h), y: k.x, w: k.h, h: k.w }));
    setRot((r) => (r + 1) % 4);
    if (aspect > 0) setAspect(1 / aspect);
  };
  const mirror = () => {
    setOps((old) => old.map((o): Op => (o.kind === 'text' ? { ...o, x: dw - o.x } : o.kind === 'arrow'
      ? { ...o, a: [dw - o.a[0], o.a[1]], b: [dw - o.b[0], o.b[1]] } : { ...o, pts: o.pts.map((p): Pt => [dw - p[0], p[1]]) })));
    setCrop((k) => ({ ...k, x: dw - k.x - k.w }));
    setFlip((f) => !f);
  };
  const reset = () => {
    setRot(0); setFlip(false); setAspect(avatar ? 1 : 0); setAspectKey(avatar ? 1 : 0); setCrop(fit(avatar ? 1 : 0, null, W, H));
    if (rot || flip) setOps([]);                                     // рисунки были в повёрнутых координатах
  };
  const pickAspect = (key: number) => {
    const a = key < 0 ? dw / dh : key;
    setAspectKey(key); setAspect(a);
    if (a > 0) setCrop(fit(a, crop, dw, dh));
  };
  const enhance = () => setAdj((a) => (a.c === 0.18 && a.s === 0.22 ? { ...a, b: 0, c: 0, s: 0 } : { ...a, b: 0.06, c: 0.18, s: 0.22 }));
  const addText = () => {
    const text = draft.trim().slice(0, 80);
    if (!text) return;
    setOps((old) => [...old, { kind: 'text', text, x: crop.x + crop.w / 2, y: crop.y + crop.h / 2, color, size: Math.max(22, crop.w / 14) }]);
    setDraft('');
  };
  const changed = rot || flip || ops.length || Object.values(adj).some(Boolean) || Math.abs(crop.w - dw) > 1 || Math.abs(crop.h - dh) > 1;
  const close = (result: string | null) => { setBase(null); setBusy(false); setShooting(false); onDone(result); };
  const finish = async () => {
    if (!base) return close(photo.uri);
    if (!avatar && !changed) return close(photo.uri);
    setBusy(true);
    if (!ops.length && !matrix(adj) && adj.v <= 0) {
      // только кадр, поворот, отражение — режем сам файл: без потери качества и без снимка экрана
      const x = Math.max(0, Math.round(crop.x)), y = Math.max(0, Math.round(crop.y));
      const actions: Action[] = [...(rot ? [{ rotate: rot * 90 }] : []), ...(flip ? [{ flip: FlipType.Horizontal }] : []),
        { crop: { originX: x, originY: y, width: Math.min(dw - x, Math.round(crop.w)), height: Math.min(dh - y, Math.round(crop.h)) } },
        ...(avatar ? [{ resize: { width: 640, height: 640 } }] : [])];
      try {
        return close((await manipulateAsync(base.uri, actions, { compress: 0.92, format: SaveFormat.JPEG })).uri);
      } catch { /* не вышло — ниже снимок области */ }
    }
    setShooting(true);
    await new Promise((r) => setTimeout(r, 120));                    // дать экрану перерисоваться без рамки
    try {
      close(await captureRef(stage, { format: 'jpg', quality: 0.92, result: 'tmpfile', ...(avatar ? { width: 640, height: 640 } : {}) }));
    } catch {
      close(photo.uri);
    }
  };

  const m = matrix(adj);
  const turn = rot === 1 ? `translate(${H} 0) rotate(90)` : rot === 2 ? `translate(${W} ${H}) rotate(180)` : rot === 3 ? `translate(0 ${W}) rotate(270)` : '';
  const transform = `${flip ? `translate(${dw} 0) scale(-1 1) ` : ''}${turn}`.trim();
  const px = 1 / scale;                                              // один пиксель экрана в единицах фото
  const k = crop, L = 22 * px;
  const hole = avatar
    ? `M${k.x + k.w} ${k.y + k.h / 2} a${k.w / 2} ${k.w / 2} 0 1 0 ${-k.w} 0 a${k.w / 2} ${k.w / 2} 0 1 0 ${k.w} 0 Z`
    : `M${k.x} ${k.y} h${k.w} v${k.h} h${-k.w} Z`;
  const round = { width: 42, height: 42, borderRadius: 21, backgroundColor: 'rgba(255,255,255,0.14)', alignItems: 'center' as const, justifyContent: 'center' as const };
  const chip = (on: boolean) => ({ height: 34, paddingHorizontal: 13, borderRadius: 17, flexDirection: 'row' as const, alignItems: 'center' as const, gap: 6,
    backgroundColor: on ? '#fff' : 'rgba(255,255,255,0.12)' });
  const cur = PARAMS.find((x) => x.key === param) ?? PARAMS[0];
  const colors = (
    <View style={{ flexDirection: 'row', gap: 8 }}>
      {COLORS.map((col) => (
        <Pressable key={col} onPress={() => setColor(col)} hitSlop={4} style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: col, borderWidth: color === col ? 3 : 1.5,
          borderColor: color === col ? '#fff' : 'rgba(255,255,255,0.35)', transform: [{ scale: color === col ? 1.15 : 1 }] }} />
      ))}
    </View>
  );
  const MODES: { key: Mode; label: string; icon: MCI }[] = [{ key: 'crop', label: 'Кадр', icon: 'crop' }, { key: 'adjust', label: 'Цвет', icon: 'tune-variant' },
    { key: 'draw', label: 'Рисунок', icon: 'pencil-outline' }, { key: 'text', label: 'Текст', icon: 'format-text' }];
  const title = avatar ? t('Фото профиля') : t(MODES.find((x) => x.key === mode)?.label ?? '');

  return (
    <Modal visible animationType="fade" onRequestClose={() => close(null)} statusBarTranslucent>
      <View style={{ flex: 1, backgroundColor: '#0b0d16', paddingTop: insets.top + 8, paddingBottom: insets.bottom + 10, paddingHorizontal: 8, gap: 8 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Pressable onPress={() => close(null)} style={round} accessibilityLabel={t('Отмена')}><MaterialCommunityIcons name="close" size={22} color="#fff" /></Pressable>
          {avatar ? <View style={{ width: 42 }} /> : (
            <Pressable onPress={() => setOps((old) => old.slice(0, -1))} disabled={!ops.length} style={[round, { opacity: ops.length ? 1 : 0.4 }]} accessibilityLabel={t('Отменить шаг')}>
              <MaterialCommunityIcons name="undo-variant" size={21} color="#fff" />
            </Pressable>
          )}
          <Text style={{ flex: 1, textAlign: 'center', color: '#fff', fontWeight: '700', fontSize: 15 }}>{title}</Text>
          <Pressable onPress={finish} disabled={busy || !base} style={{ height: 40, paddingHorizontal: 18, borderRadius: 20, backgroundColor: c.accent, alignItems: 'center', justifyContent: 'center', opacity: busy || !base ? 0.6 : 1 }}>
            <Text style={{ color: '#fff', fontSize: 15, fontWeight: '800' }}>{doneLabel ?? t('Готово')}</Text>
          </Pressable>
        </View>

        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          {!base ? <ActivityIndicator color="#fff" /> : (
            <View ref={stage} collapsable={false} style={{ width: sw, height: sh, overflow: 'hidden', backgroundColor: '#000' }} {...pan.panHandlers}>
              <Svg width={sw} height={sh} viewBox={`${region.x} ${region.y} ${region.w} ${region.h}`} pointerEvents="none">
                <Defs>
                  {m ? <Filter id="adj"><FeColorMatrix in="SourceGraphic" type="matrix" values={m} /></Filter> : null}
                  <RadialGradient id="vig" cx="50%" cy="50%" r="74%">
                    <Stop offset="0.38" stopColor="#000" stopOpacity={0} />
                    <Stop offset="1" stopColor="#000" stopOpacity={adj.v * 0.78} />
                  </RadialGradient>
                </Defs>
                <G transform={transform || undefined}>
                  <SvgImage x={0} y={0} width={W} height={H} href={{ uri: base.uri }} preserveAspectRatio="none" filter={m ? 'url(#adj)' : undefined} />
                </G>
                {adj.v > 0 ? <Rect x={k.x} y={k.y} width={k.w} height={k.h} fill="url(#vig)" /> : null}
                {ops.map((o, i) => {
                  if (o.kind === 'text') {
                    return (
                      <SvgText key={i} x={o.x} y={o.y + o.size * 0.34} fontSize={o.size} fontWeight="700" textAnchor="middle" fill={o.color}
                        stroke={o.color === '#111827' ? '#fff' : 'rgba(0,0,0,0.55)'} strokeWidth={o.size / 22}>{o.text}</SvgText>
                    );
                  }
                  if (o.kind === 'arrow') {
                    const ang = Math.atan2(o.b[1] - o.a[1], o.b[0] - o.a[0]), hd = o.w * 4.2;
                    const head = `${o.b[0]},${o.b[1]} ${o.b[0] - hd * Math.cos(ang - 0.45)},${o.b[1] - hd * Math.sin(ang - 0.45)} ${o.b[0] - hd * Math.cos(ang + 0.45)},${o.b[1] - hd * Math.sin(ang + 0.45)}`;
                    return <G key={i}><Line x1={o.a[0]} y1={o.a[1]} x2={o.b[0]} y2={o.b[1]} stroke={o.color} strokeWidth={o.w} strokeLinecap="round" /><Polygon points={head} fill={o.color} /></G>;
                  }
                  const d = o.pts.map((p, n) => `${n ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ') + (o.pts.length === 1 ? ' l0.1 0' : '');
                  return <Path key={i} d={d} stroke={o.color} strokeOpacity={o.marker ? 0.42 : 1} strokeWidth={o.w} strokeLinecap="round" strokeLinejoin="round" fill="none" />;
                })}
                {mode === 'crop' && !shooting ? (
                  <G>
                    <Path d={`M0 0 H${dw} V${dh} H0 Z ${hole}`} fill="rgba(11,13,22,0.66)" fillRule="evenodd" />
                    <Rect x={k.x} y={k.y} width={k.w} height={k.h} fill="none" stroke="rgba(255,255,255,0.95)" strokeWidth={1.5 * px} />
                    {[1, 2].map((i) => (
                      <G key={i}>
                        <Line x1={k.x + (k.w * i) / 3} y1={k.y} x2={k.x + (k.w * i) / 3} y2={k.y + k.h} stroke="rgba(255,255,255,0.35)" strokeWidth={px} />
                        <Line x1={k.x} y1={k.y + (k.h * i) / 3} x2={k.x + k.w} y2={k.y + (k.h * i) / 3} stroke="rgba(255,255,255,0.35)" strokeWidth={px} />
                      </G>
                    ))}
                    {([[k.x, k.y, 1, 1], [k.x + k.w, k.y, -1, 1], [k.x, k.y + k.h, 1, -1], [k.x + k.w, k.y + k.h, -1, -1]] as const).map(([x, y, sx, sy], i) => (
                      <Path key={i} d={`M${x + sx * L} ${y} L${x} ${y} L${x} ${y + sy * L}`} stroke="#fff" strokeWidth={4 * px} strokeLinecap="round" fill="none" />
                    ))}
                  </G>
                ) : null}
              </Svg>
            </View>
          )}
        </View>

        <View style={{ minHeight: 92, justifyContent: 'center', gap: 8 }}>
          {mode === 'crop' ? (
            <>
              {avatar ? <Text style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12.5, textAlign: 'center' }}>{t('Двигайте рамку и тяните за углы')}</Text> : (
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
                  {ASPECTS.map((a) => (
                    <Pressable key={a.label} onPress={() => pickAspect(a.key)} style={chip(aspectKey === a.key)}>
                      <Text style={{ color: aspectKey === a.key ? '#111' : '#fff', fontWeight: '700', fontSize: 13.5 }}>{a.key > 0 ? a.label : t(a.label)}</Text>
                    </Pressable>
                  ))}
                </ScrollView>
              )}
              <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 8 }}>
                <Pressable onPress={rotate} style={[round, { borderRadius: 14 }]} accessibilityLabel={t('Повернуть')}><MaterialCommunityIcons name="rotate-right" size={22} color="#fff" /></Pressable>
                <Pressable onPress={mirror} style={[round, { borderRadius: 14 }]} accessibilityLabel={t('Отразить')}><MaterialCommunityIcons name="flip-horizontal" size={22} color="#fff" /></Pressable>
                <Pressable onPress={reset} style={{ height: 42, borderRadius: 14, paddingHorizontal: 14, backgroundColor: 'rgba(255,255,255,0.14)', alignItems: 'center', justifyContent: 'center' }}><Text style={{ color: '#fff', fontWeight: '700' }}>{t('Сбросить')}</Text></Pressable>
              </View>
            </>
          ) : mode === 'adjust' ? (
            <>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
                {PARAMS.map((x) => (
                  <Pressable key={x.key} onPress={() => setParam(x.key)} style={[chip(param === x.key), adj[x.key] && param !== x.key ? { borderWidth: 1.5, borderColor: c.accent } : null]}>
                    <MaterialCommunityIcons name={x.icon} size={16} color={param === x.key ? '#111' : '#fff'} />
                    <Text style={{ color: param === x.key ? '#111' : '#fff', fontWeight: '700', fontSize: 13.5 }}>{t(x.label)}</Text>
                  </Pressable>
                ))}
              </ScrollView>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 6 }}>
                <Slider value={adj[param]} min={cur.min} onChange={(v) => setAdj((a) => ({ ...a, [param]: v }))} />
                <Text style={{ width: 34, textAlign: 'right', color: 'rgba(255,255,255,0.8)', fontSize: 13 }}>{Math.round(adj[param] * 100)}</Text>
                <Pressable onPress={enhance} style={{ height: 42, borderRadius: 14, paddingHorizontal: 12, flexDirection: 'row', gap: 6, backgroundColor: 'rgba(255,255,255,0.14)', alignItems: 'center', justifyContent: 'center' }}>
                  <MaterialCommunityIcons name="auto-fix" size={18} color="#fff" /><Text style={{ color: '#fff', fontWeight: '700' }}>{t('Улучшить')}</Text>
                </Pressable>
              </View>
            </>
          ) : mode === 'draw' ? (
            <>
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <View style={{ flexDirection: 'row', gap: 6 }}>
                  {([['pen', 'pencil-outline', 'Карандаш'], ['marker', 'marker', 'Маркер'], ['arrow', 'arrow-top-right', 'Стрелка']] as const).map(([key, icon, label]) => (
                    <Pressable key={key} onPress={() => setTool(key)} accessibilityLabel={t(label)} style={[round, { borderRadius: 14, backgroundColor: tool === key ? '#fff' : 'rgba(255,255,255,0.14)' }]}>
                      <MaterialCommunityIcons name={icon} size={21} color={tool === key ? '#111' : '#fff'} />
                    </Pressable>
                  ))}
                </View>
                {colors}
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 6 }}>
                <Text style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12.5 }}>{t('Толщина')}</Text>
                <Slider value={(size - 1) / 5} min={0} onChange={(v) => setSize(1 + v * 5)} />
              </View>
            </>
          ) : (
            <>
              <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
                <TextInput value={draft} onChangeText={setDraft} maxLength={80} placeholder={t('Напишите текст')} placeholderTextColor="rgba(255,255,255,0.5)"
                  onSubmitEditing={addText} returnKeyType="done"
                  style={{ flex: 1, height: 42, borderRadius: 14, paddingHorizontal: 14, backgroundColor: 'rgba(255,255,255,0.14)', color: '#fff', fontSize: 16 }} />
                <Pressable onPress={addText} style={{ height: 42, paddingHorizontal: 14, borderRadius: 14, backgroundColor: c.accent, alignItems: 'center', justifyContent: 'center' }}>
                  <Text style={{ color: '#fff', fontWeight: '700' }}>{t('Добавить')}</Text>
                </Pressable>
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                {colors}
                <Text style={{ flex: 1, color: 'rgba(255,255,255,0.6)', fontSize: 12.5 }} numberOfLines={2}>{t('Надпись можно двигать пальцем')}</Text>
              </View>
            </>
          )}
        </View>

        {avatar ? null : (
          <View style={{ flexDirection: 'row', borderTopWidth: 0.5, borderTopColor: 'rgba(255,255,255,0.14)', paddingTop: 6 }}>
            {MODES.map((x) => (
              <Pressable key={x.key} onPress={() => setMode(x.key)} style={{ flex: 1, alignItems: 'center', gap: 3, paddingVertical: 6, borderRadius: 12, backgroundColor: mode === x.key ? 'rgba(255,255,255,0.1)' : 'transparent' }}>
                <MaterialCommunityIcons name={x.icon} size={21} color={mode === x.key ? '#fff' : 'rgba(255,255,255,0.6)'} />
                <Text style={{ fontSize: 11.5, fontWeight: '700', color: mode === x.key ? '#fff' : 'rgba(255,255,255,0.6)' }}>{t(x.label)}</Text>
              </Pressable>
            ))}
          </View>
        )}
      </View>
    </Modal>
  );
}

/**
 * Выбор аватара как в Telegram: фото из галереи → свой редактор (рамка-квадрат с кругом, поворот, отражение) → готовый квадрат.
 * const { pick, editor } = useAvatarPick((uri) => …);  — editor нужно вставить в разметку экрана.
 */
export function useAvatarPick(onPicked: (uri: string) => void) {
  const [photo, setPhoto] = useState<EditPhoto | null>(null);
  const pick = async () => {
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.9 });
    const a = r.canceled ? null : r.assets[0];
    if (a) setPhoto({ uri: a.uri, width: a.width, height: a.height });
  };
  const editor = <PhotoEditor avatar photo={photo} onDone={(uri) => { setPhoto(null); if (uri) onPicked(uri); }} />;
  return { pick, editor };
}
