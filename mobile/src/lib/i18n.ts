/** Языки приложения: русский (исходный текст), узбекский, английский.
 *  t('Русский текст', {n: 5}) → перевод из locales/uz.ts или locales/en.ts, либо сам текст. */
import en from './locales/en';
import uz from './locales/uz';

export type Lang = 'ru' | 'uz' | 'en';
export const LANGS: { code: Lang; name: string }[] = [
  { code: 'ru', name: 'Русский' },
  { code: 'uz', name: 'Oʻzbekcha' },
  { code: 'en', name: 'English' },
];
const DICT: Record<Lang, Record<string, string>> = { ru: {}, uz, en };

let current: Lang = 'ru';

export function setLang(l: Lang) {
  current = DICT[l] ? l : 'ru';
}
export function getLang(): Lang {
  return current;
}

export function t(s: string, vars?: Record<string, string | number>): string {
  let out = DICT[current][s] ?? s;
  if (vars) for (const [k, v] of Object.entries(vars)) out = out.split(`{${k}}`).join(String(v));
  return out;
}

/** Язык телефона → язык приложения (если поддерживаем). */
export function deviceLang(): Lang {
  try {
    const loc = Intl.DateTimeFormat().resolvedOptions().locale.slice(0, 2).toLowerCase();
    return (['ru', 'uz', 'en'] as Lang[]).includes(loc as Lang) ? (loc as Lang) : 'ru';
  } catch {
    return 'ru';
  }
}
