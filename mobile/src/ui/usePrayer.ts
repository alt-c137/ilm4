/** Время намаза «сейчас»: сегодняшнее расписание, следующий намаз и живой отсчёт. */
import { useEffect, useMemo, useState } from 'react';

import { currentPrayer, dayTimes, nextPrayer } from '@/lib/prayer';
import { useApp } from '@/state/app';

export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

export function usePrayerNow() {
  const { prayer } = useApp();
  const now = useNow(1000);
  const minute = Math.floor(now.getTime() / 60000);
  const place = prayer.place;
  const base = useMemo(() => {
    if (!place) return null;
    const d = new Date(minute * 60000);
    const next = nextPrayer(place, d, prayer.method, prayer.asr);
    return { today: next.today, next, current: currentPrayer(next.today, d) };
  }, [place, prayer.method, prayer.asr, minute]);
  if (!base) return null;
  const left = Math.max(0, Math.floor((base.next.at.getTime() - now.getTime()) / 1000));
  return { ...base, left, now };
}

export function fmtLeft(sec: number) {
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
}

export { dayTimes };
