/** Ползунки: одинарный и двойной «от — до» (возраст, рост, вес). */
import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { View, type LayoutChangeEvent } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';

import { useApp } from '@/state/app';

import { Txt } from './kit';

const THUMB = 28;

export function RangeSlider({ min, max, value, onChange, label, unit = '', single = false }: {
  min: number; max: number; value: [number, number]; onChange: (v: [number, number]) => void; label?: string; unit?: string; single?: boolean;
}) {
  'use no memo';
  const { c } = useApp();
  const [w, setW] = useState(0);
  const span = max - min;
  const toX = (v: number) => ((v - min) / span) * Math.max(1, w - THUMB);
  const [lo, hi] = value;

  // жесты создаются один раз; текущие значения — через ref (иначе при перерисовке во время
  // перетаскивания ползунок «прыгал» бы к началу)
  const live = useRef({ lo, hi, w, start: 0, onChange, single });
  useLayoutEffect(() => {
    live.current = { ...live.current, lo, hi, w, onChange, single };
  });

  const gestures = useMemo(() => {
    const make = (which: 0 | 1) => Gesture.Pan()
      .runOnJS(true)
      .hitSlop(14)
      .onBegin(() => {
        const L = live.current;
        const x = (v: number) => ((v - min) / span) * Math.max(1, L.w - THUMB);
        L.start = which === 0 ? x(L.lo) : x(L.hi);
      })
      .onUpdate((e) => {
        const L = live.current;
        const pos = Math.min(Math.max(0, L.start + e.translationX), L.w - THUMB);
        const v = Math.round(min + (pos / Math.max(1, L.w - THUMB)) * span);
        if (L.single) L.onChange([v, v]);
        else L.onChange(which === 0 ? [Math.min(v, L.hi), L.hi] : [L.lo, Math.max(v, L.lo)]);
      });
    // eslint-disable-next-line react-hooks/refs -- ref читается только в обработчиках жестов, не при отрисовке
    return [make(0), make(1)] as const;
  }, [min, span]);

  const thumb = (which: 0 | 1) => (
    <GestureDetector gesture={gestures[which]}>
      <View style={{
        position: 'absolute', left: toX(which === 0 ? lo : hi), top: 0, width: THUMB, height: THUMB, borderRadius: THUMB / 2,
        backgroundColor: '#fff', borderWidth: 3, borderColor: c.accent, shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 4, elevation: 3,
      }} />
    </GestureDetector>
  );

  return (
    <View style={{ gap: 8 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        {label ? <Txt kind="h3" style={{ fontWeight: '600' }}>{label}</Txt> : <View />}
        <Txt kind="h3" color={c.accentD}>{single ? `${lo}${unit}` : `${lo}–${hi}${unit}`}</Txt>
      </View>
      <View style={{ height: THUMB, justifyContent: 'center' }} onLayout={(e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width)}>
        <View style={{ height: 6, borderRadius: 3, backgroundColor: c.line, marginHorizontal: THUMB / 2 }} />
        {w ? (
          <View style={{ position: 'absolute', height: 6, borderRadius: 3, backgroundColor: c.accent,
            left: (single ? 0 : toX(lo)) + THUMB / 2, width: toX(hi) - (single ? 0 : toX(lo)) }} />
        ) : null}
        {w && !single ? thumb(0) : null}
        {w ? thumb(1) : null}
      </View>
    </View>
  );
}
