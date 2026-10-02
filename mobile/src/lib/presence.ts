/** «в сети», «был(а) в 14:05», «был(а) недавно» — подпись под именем, как в Telegram. */
export type Presence = { online: boolean; seen: string | null; hidden: boolean };

const MONTHS: Record<string, string[]> = {
  ru: ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
  uz: ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'],
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
};

type T = (s: string, vars?: Record<string, string | number>) => string;

export function statusText(pr: Presence | null | undefined, t: T, lang: string): string {
  if (!pr) return '';
  if (pr.online) return t('в сети');
  if (pr.hidden) return t('был(а) недавно');
  if (!pr.seen) return t('был(а) давно');
  const d = new Date(pr.seen);
  const now = new Date();
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  const days = Math.round((new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
    - new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()) / 86400000);
  if (days <= 0) return t('был(а) в {t}', { t: hm });
  if (days === 1) return t('был(а) вчера в {t}', { t: hm });
  const m = (MONTHS[lang] ?? MONTHS.ru)[d.getMonth()];
  const date = lang === 'en' ? `${m} ${d.getDate()}` : lang === 'uz' ? `${d.getDate()}-${m}` : `${d.getDate()} ${m}`;
  if (days < 300) return t('был(а) {d} в {t}', { d: date, t: hm });
  return t('был(а) {d}', { d: `${date} ${d.getFullYear()}` });
}
