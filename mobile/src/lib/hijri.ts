/** Дата по хиджре. Сначала — календарь Умм аль-Кура из системы (Intl);
 *  если телефон его не знает — табличный расчёт (может отличаться на ±1 день). */
import { getLang, t } from './i18n';

const MONTHS: Record<string, string[]> = {
  ru: ['мухаррам', 'сафар', 'раби-уль-авваль', 'раби-уль-ахир', 'джумада-уль-уля', 'джумада-ль-ахира', 'раджаб',
    'шаабан', 'рамадан', 'шавваль', 'зуль-када', 'зуль-хиджа'],
  uz: ['muharram', 'safar', 'rabiul avval', 'rabiul oxir', 'jumodul avval', 'jumodul oxir', 'rajab', 'shaʼbon',
    'ramazon', 'shavvol', 'zulqaʼda', 'zulhijja'],
  en: ['Muharram', 'Safar', 'Rabi al-Awwal', 'Rabi al-Thani', 'Jumada al-Ula', 'Jumada al-Akhirah', 'Rajab',
    'Shaaban', 'Ramadan', 'Shawwal', 'Dhu al-Qadah', 'Dhu al-Hijjah'],
};

export type Hijri = { day: number; month: number; year: number };

function tabular(date: Date): Hijri {
  const jd = Math.floor(date.getTime() / 86400000 + 2440587.5) + 0.5;
  const l0 = Math.floor(jd - 1948439.5) + 10632;
  const n = Math.floor((l0 - 1) / 10631);
  let l = l0 - 10631 * n + 354;
  const j = Math.floor((10985 - l) / 5316) * Math.floor((50 * l) / 17719) + Math.floor(l / 5670) * Math.floor((43 * l) / 15238);
  l = l - Math.floor((30 - j) / 15) * Math.floor((17719 * j) / 50) - Math.floor(j / 16) * Math.floor((15238 * j) / 43) + 29;
  const month = Math.floor((24 * l) / 709);
  const day = l - Math.floor((709 * month) / 24);
  const year = 30 * n + j - 30;
  return { day, month, year };
}

export function toHijri(date: Date): Hijri {
  try {
    const parts = new Intl.DateTimeFormat('en-u-ca-islamic-umalqura', { day: 'numeric', month: 'numeric', year: 'numeric' })
      .formatToParts(date);
    const get = (k: string) => Number(parts.find((p) => p.type === k)?.value);
    const h = { day: get('day'), month: get('month'), year: get('year') };
    if (h.day && h.month && h.year > 1300 && h.year < 1600) return h;
  } catch {
    /* нет календаря в системе */
  }
  return tabular(date);
}

export function hijriText(date: Date): string {
  const h = toHijri(date);
  const names = MONTHS[getLang()] ?? MONTHS.ru;
  return `${h.day} ${names[h.month - 1]} ${h.year} ${t('г. х.')}`;
}

const WEEK: Record<string, string[]> = {
  ru: ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'],
  uz: ['yakshanba', 'dushanba', 'seshanba', 'chorshanba', 'payshanba', 'juma', 'shanba'],
  en: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
};
const GMONTHS: Record<string, string[]> = {
  ru: ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
  uz: ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'],
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
};

/** «Четверг, 24 сентября» — свои названия: Intl на телефонах не всегда знает узбекский. */
export function gregText(date: Date): string {
  const l = getLang();
  const w = WEEK[l][date.getDay()], m = GMONTHS[l][date.getMonth()], d = date.getDate();
  const s = l === 'en' ? `${w}, ${m} ${d}` : l === 'uz' ? `${w}, ${d}-${m}` : `${w}, ${d} ${m}`;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function shortDate(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const same = d.toDateString() === now.toDateString();
  const hh = String(d.getHours()).padStart(2, '0'), mm = String(d.getMinutes()).padStart(2, '0');
  if (same) return `${hh}:${mm}`;
  const y = new Date(now.getTime() - 86400000);
  if (d.toDateString() === y.toDateString()) return t('вчера');
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getFullYear()).slice(2)}`;
}
