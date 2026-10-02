/**
 * Время намаза — считается на телефоне, без интернета.
 * Порт алгоритма PrayTimes.org (тот же, что на сайте ilm4: apps/prayer/services.py),
 * поэтому время в приложении и на сайте совпадает до минуты.
 */

export type PrayerKey = 'fajr' | 'sunrise' | 'dhuhr' | 'asr' | 'maghrib' | 'isha';
export const PRAYER_KEYS: PrayerKey[] = ['fajr', 'sunrise', 'dhuhr', 'asr', 'maghrib', 'isha'];
export const FARD: PrayerKey[] = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha'];

export type Method = 'Karachi' | 'MWL' | 'ISNA' | 'Makkah' | 'Egypt';
export type Asr = 'standard' | 'hanafi';

const ANGLES: Record<Method, { fajr: number; isha: number | null }> = {
  Karachi: { fajr: 18, isha: 18 },
  MWL: { fajr: 18, isha: 17 },
  ISNA: { fajr: 15, isha: 15 },
  Egypt: { fajr: 19.5, isha: 17.5 },
  Makkah: { fajr: 18.5, isha: null }, // Иша = Магриб + 90 минут
};

const rad = (d: number) => (d * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;
const sin = (d: number) => Math.sin(rad(d));
const cos = (d: number) => Math.cos(rad(d));
const tan = (d: number) => Math.tan(rad(d));
const arcsin = (x: number) => deg(Math.asin(x));
const arccos = (x: number) => deg(Math.acos(x));
const arccot = (x: number) => deg(Math.atan(1 / x));
const arctan2 = (y: number, x: number) => deg(Math.atan2(y, x));
const fix = (a: number, m: number) => {
  if (Number.isNaN(a)) return a;
  a = a - m * Math.floor(a / m);
  return a < 0 ? a + m : a;
};
const fixangle = (a: number) => fix(a, 360);
const fixhour = (h: number) => fix(h, 24);

function julian(y: number, m: number, d: number) {
  if (m <= 2) {
    y -= 1;
    m += 12;
  }
  const A = Math.floor(y / 100);
  const B = 2 - A + Math.floor(A / 4);
  return Math.floor(365.25 * (y + 4716)) + Math.floor(30.6001 * (m + 1)) + d + B - 1524.5;
}

function sunPosition(jd: number) {
  const D = jd - 2451545.0;
  const g = fixangle(357.529 + 0.98560028 * D);
  const q = fixangle(280.459 + 0.98564736 * D);
  const L = fixangle(q + 1.915 * sin(g) + 0.02 * sin(2 * g));
  const e = 23.439 - 0.00000036 * D;
  const RA = arctan2(cos(e) * sin(L), cos(L)) / 15;
  const eqt = q / 15 - fixhour(RA);
  const decl = arcsin(sin(e) * sin(L));
  return { decl, eqt };
}

/** Сырые часы (дробные) на дату по координатам и смещению UTC. */
export function computeHours(
  date: { y: number; m: number; d: number },
  lat: number,
  lng: number,
  tz: number,
  method: Method = 'Karachi',
  asr: Asr = 'standard',
): Record<PrayerKey, number> {
  const jDate = julian(date.y, date.m, date.d) - lng / (15 * 24);
  const a = ANGLES[method] ?? ANGLES.Karachi;
  const midDay = (t: number) => fixhour(12 - sunPosition(jDate + t).eqt);
  const sunAngleTime = (angle: number, t: number, ccw = false) => {
    const decl = sunPosition(jDate + t).decl;
    const noon = midDay(t);
    const x = (-sin(angle) - sin(decl) * sin(lat)) / (cos(decl) * cos(lat));
    if (x < -1 || x > 1) return NaN;
    const T = arccos(x) / 15;
    return noon + (ccw ? -T : T);
  };
  const asrTime = (factor: number, t: number) => {
    const decl = sunPosition(jDate + t).decl;
    return sunAngleTime(-arccot(factor + tan(Math.abs(lat - decl))), t);
  };
  const riseSet = 0.833;
  // одна итерация от стартовых приближений (как в оригинале, numIterations = 1)
  const p = { fajr: 5 / 24, sunrise: 6 / 24, dhuhr: 12 / 24, asr: 13 / 24, sunset: 18 / 24, maghrib: 18 / 24, isha: 18 / 24 };
  const t: Record<string, number> = {
    fajr: sunAngleTime(a.fajr, p.fajr, true),
    sunrise: sunAngleTime(riseSet, p.sunrise, true),
    dhuhr: midDay(p.dhuhr),
    asr: asrTime(asr === 'hanafi' ? 2 : 1, p.asr),
    sunset: sunAngleTime(riseSet, p.sunset),
    maghrib: sunAngleTime(0, p.maghrib), // «0 min» — магриб = закат (ниже заменяется)
    isha: sunAngleTime(a.isha ?? 18, p.isha),
  };
  const adj = tz - lng / 15;
  for (const k of Object.keys(t)) t[k] += adj;
  // высокие широты: «середина ночи»
  const night = fixhour(t.sunrise - t.sunset);
  const portion = night / 2;
  const hl = (time: number, base: number, ccw: boolean) => {
    const diff = ccw ? fixhour(base - time) : fixhour(time - base);
    return Number.isNaN(time) || diff > portion ? base + (ccw ? -portion : portion) : time;
  };
  t.fajr = hl(t.fajr, t.sunrise, true);
  t.isha = hl(t.isha, t.sunset, false);
  t.maghrib = t.sunset;
  if (a.isha === null) t.isha = t.maghrib + 90 / 60;
  return { fajr: t.fajr, sunrise: t.sunrise, dhuhr: t.dhuhr, asr: t.asr, maghrib: t.maghrib, isha: t.isha };
}

/** «04:34» — с тем же округлением, что на сайте. */
export function fmt(h: number): string {
  if (Number.isNaN(h)) return '--:--';
  const x = fixhour(h + 0.5 / 60);
  const hh = Math.floor(x);
  const mm = Math.floor((x - hh) * 60);
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
}

export type Place = { lat: number; lon: number; tz: number | null; name: string };

/** Смещение UTC в часах для даты: у города — фиксированное, у GPS — зона телефона. */
export function tzFor(place: Place, day: Date): number {
  return place.tz ?? -day.getTimezoneOffset() / 60;
}

export type DayTimes = { date: Date; times: Record<PrayerKey, string>; at: Record<PrayerKey, Date> };

/** Времена на день + точные моменты (Date) — для отсчёта и напоминаний. */
export function dayTimes(place: Place, day: Date, method: Method, asr: Asr): DayTimes {
  const tz = tzFor(place, day);
  // календарная дата в зоне места
  const local = new Date(day.getTime() + tz * 3600_000);
  const y = local.getUTCFullYear(), m = local.getUTCMonth() + 1, d = local.getUTCDate();
  const hours = computeHours({ y, m, d }, place.lat, place.lon, tz, method, asr);
  const times = {} as Record<PrayerKey, string>;
  const at = {} as Record<PrayerKey, Date>;
  for (const k of PRAYER_KEYS) {
    const s = fmt(hours[k]);
    times[k] = s;
    const [hh, mm] = s.split(':').map(Number);
    at[k] = new Date(Date.UTC(y, m - 1, d, hh, mm) - tz * 3600_000);
  }
  return { date: new Date(Date.UTC(y, m - 1, d)), times, at };
}

/** Следующий намаз (восход пропускаем) и сколько до него. */
export function nextPrayer(place: Place, now: Date, method: Method, asr: Asr) {
  const today = dayTimes(place, now, method, asr);
  for (const k of FARD) if (today.at[k] > now) return { key: k, at: today.at[k], today };
  const tomorrow = dayTimes(place, new Date(now.getTime() + 86400_000), method, asr);
  return { key: 'fajr' as PrayerKey, at: tomorrow.at.fajr, today };
}

/** Текущий намаз (чьё время идёт сейчас) — для подсветки. */
export function currentPrayer(today: DayTimes, now: Date): PrayerKey | null {
  let cur: PrayerKey | null = null;
  for (const k of FARD) if (today.at[k] <= now) cur = k;
  if (cur === 'fajr' && today.at.sunrise <= now) return null; // после восхода до зухра — не время фарда
  return cur ?? 'isha';
}

/** Направление на Каабу (градусы от севера по часовой). */
export function qiblaBearing(lat: number, lon: number): number {
  const kLat = rad(21.4225), kLon = rad(39.8262);
  const la = rad(lat), dl = kLon - rad(lon);
  const b = Math.atan2(Math.sin(dl), Math.cos(la) * Math.tan(kLat) - Math.sin(la) * Math.cos(dl));
  return (deg(b) + 360) % 360;
}

/** Расстояние по прямой, км. */
export function distanceKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
  const R = 6371;
  const dLat = rad(b.lat - a.lat), dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
