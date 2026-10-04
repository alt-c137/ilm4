/** Общее состояние приложения: язык, тема, вход, настройки сервера, намаз, сеть. */
import NetInfo from '@react-native-community/netinfo';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AppState, useColorScheme } from 'react-native';

import { api, cachedGet, onAuthLost, onReachability, setApiCurrency, setApiLang, setApiToken } from '@/lib/api';
import { deviceLang, setLang as setI18nLang, t as translate, type Lang } from '@/lib/i18n';
import { registerPush, schedulePrayers, type PrayerAlerts } from '@/lib/notify';
import type { Asr, Method, Place } from '@/lib/prayer';
import { clearCache, getAccounts, getToken, load, MAX_ACCOUNTS, save, setAccounts, setToken, type SavedAccount } from '@/lib/storage';
import { palettes, type Colors } from '@/lib/theme';

export type Module = { key: string; name: string; status: 'on' | 'soon'; emoji: string; icon: string; descr: string; group: string; native: boolean };
export type Config = {
  site_name: string; site_url: string; min_version: string; notice: string; bot: string; map?: { maptiler: string };
  modules: Module[]; groups: { key: string; name: string }[];
  features: {
    chat: Record<'photo' | 'video' | 'voice' | 'circle' | 'calls' | 'video_calls', boolean>;
    nikah: { premium: boolean; daily_limit: number; premium_price: number; premium_days: number; restore_price: number; chat_price: number; photo_minutes: number };
    telegram_login: boolean; hadith: boolean; groups?: boolean; channels?: boolean;
  };
  prayer: { cities: { key: string; name: string; lat: number; lon: number; tz: number }[]; methods: { key: Method; name: string }[] };
  links: Record<string, string>;
  currencies?: { code: string; name: string; sign: string }[]; currency?: string;
};
export type Privacy = 'all' | 'close' | 'nobody';
export type SocialLink = { kind: string; title?: string; value: string; show?: string; url?: string; privacy?: Privacy };
export type User = {
  id: number; name: string; nickname: string; first_name: string; email: string; city: string; phone: string;
  language: string; currency?: string; currency_now?: string; avatar: string; telegram: boolean; verified: boolean; balance: number | null;
  phone_verified?: boolean; needs_phone?: { publish: boolean; nikah: boolean };
  last_name?: string; ui?: { tabs_app?: string[] };
  handle?: string; bio?: string; privacy?: { phone: Privacy; seen: Privacy; find_by_phone: boolean; forward?: Privacy; invite?: Privacy; counts?: Privacy; private?: boolean }; links?: SocialLink[]; links_view?: string; links_mode?: string;
  nikah: { id: number; status: string; active: boolean; gender: 'M' | 'F' } | null;
};
/** Фон переписки: узор, цвет или своё фото (хранится на телефоне, как обои в Telegram). */
export type Wall = { pattern?: 'shapes' | 'dots' | 'waves' | 'grid' | 'bubbles' | 'none'; color?: string; photo?: string; blur?: number; dim?: number };
/** Нижние кнопки, которые человек выбрал сам; «Профиль» всегда последний. */
export const TAB_KEYS = ['home', 'feed', 'communities', 'prayer', 'services', 'chats', 'tracker', 'nikah', 'map', 'buy', 'news', 'jobs', 'transport', 'forum', 'library'] as const;
export const TAB_SLOTS = 20;                // сколько угодно: больше пяти — панель листается пальцем
export type TabKey = typeof TAB_KEYS[number];
export const DEFAULT_TABS: TabKey[] = ['home', 'prayer', 'services', 'chats'];
export type PrayerSettings = {
  place: (Place & { key: string; gps?: boolean }) | null; method: Method; asr: Asr; alerts: PrayerAlerts;
};
type ThemeMode = 'system' | 'light' | 'dark';

const DEFAULT_PRAYER: PrayerSettings = {
  place: { key: 'tashkent', name: 'Ташкент', lat: 41.3111, lon: 69.2797, tz: 5 },
  method: 'Karachi', asr: 'standard',
  alerts: { enabled: { fajr: true, dhuhr: true, asr: true, maghrib: true, isha: true }, before: 0 },
};

type Ctx = {
  ready: boolean; lang: Lang; setLang: (l: Lang) => void; t: typeof translate;
  themeMode: ThemeMode; setThemeMode: (m: ThemeMode) => void; dark: boolean; c: Colors;
  config: Config | null; refreshConfig: () => Promise<void>; moduleOn: (key: string) => boolean;
  user: User | null; signIn: (token: string, user: User) => Promise<void>; signOut: () => Promise<void>;
  refreshMe: () => Promise<void>; setUser: (u: User) => void;
  /** несколько аккаунтов, как в Telegram: кто вошёл на этом устройстве и переключение без пароля */
  accounts: SavedAccount[]; switchAccount: (id: number) => Promise<void>; canAddAccount: boolean;
  prayer: PrayerSettings; setPrayer: (p: Partial<PrayerSettings>) => void;
  online: boolean; langTick: number;
  currency: string; setCurrency: (code: string) => void;
  tabs: TabKey[]; setTabs: (keys: TabKey[]) => void;
  introSeen: boolean; finishIntro: () => void;
  wall: Wall; setWall: (w: Wall) => void;
};

const AppContext = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const system = useColorScheme();
  const [ready, setReady] = useState(false);
  const [lang, setLangState] = useState<Lang>('ru');
  const [langTick, setLangTick] = useState(0);
  const [themeMode, setThemeModeState] = useState<ThemeMode>('system');
  const [config, setConfig] = useState<Config | null>(null);
  const [currency, setCurrencyState] = useState('');     // '' — определять автоматически
  const [user, setUserState] = useState<User | null>(null);
  const [accounts, setAccountsState] = useState<SavedAccount[]>([]);
  const [prayer, setPrayerState] = useState<PrayerSettings>(DEFAULT_PRAYER);
  const [online, setOnline] = useState(true);
  const [tabs, setTabsState] = useState<TabKey[]>(DEFAULT_TABS);
  const [introSeen, setIntroSeen] = useState(true);
  const [wall, setWallState] = useState<Wall>({});
  const prayerRef = useRef(prayer);

  const applyLang = (l: Lang) => {
    setI18nLang(l);
    setApiLang(l);
    setLangState(l);
    setLangTick((x) => x + 1);
  };

  const refreshConfig = useCallback(async () => {
    try {
      const { data } = await cachedGet<Config>('/config/');
      setConfig(data);
      // название города — на языке приложения (в настройках могло остаться на прежнем)
      const place = prayerRef.current.place;
      const city = place && !place.gps ? data.prayer.cities.find((x) => x.key === place.key) : null;
      if (city && city.name !== place!.name) {
        const next = { ...prayerRef.current, place: { ...place!, name: city.name } };
        prayerRef.current = next;
        setPrayerState(next);
        save('prayer', next);
      }
    } catch {
      /* офлайн без кеша — работаем с тем, что есть (намаз считается без сервера) */
    }
  }, []);

  const refreshMe = useCallback(async () => {
    try {
      const { data } = await cachedGet<User>('/me/');
      setUserState(data);
      save('user', data);
      const remote = (data.ui?.tabs_app ?? []).filter((k): k is TabKey => (TAB_KEYS as readonly string[]).includes(k));
      if (remote.length >= 2 && !(await load<TabKey[] | null>('tabs', null))) {
        setTabsState(remote);
        save('tabs', remote);
      }
    } catch {
      /* 401 обработает onAuthLost */
    }
  }, []);

  const keepAccounts = useCallback(async (list: SavedAccount[]) => { setAccountsState(list); await setAccounts(list); }, []);

  /** Открыть другой аккаунт, уже вошедший на этом устройстве. */
  const switchAccount = useCallback(async (id: number) => {
    const list = await getAccounts();
    const next = list.find((a) => a.id === id);
    if (!next) return;
    await setToken(next.token);
    setApiToken(next.token);
    await clearCache();
    try {
      const me = await api<User>('/me/');
      setUserState(me);
      save('user', me);
    } catch {
      await keepAccounts(list.filter((a) => a.id !== id));      // вход устарел — убираем из списка
      await setToken(null);
      setApiToken(null);
      setUserState(null);
      save('user', null);
    }
  }, [keepAccounts]);

  const signOut = useCallback(async () => {
    const token = await getToken();
    try {
      await api('/auth/logout/', { body: {} });
    } catch {
      /* офлайн — токен всё равно забываем */
    }
    const rest = (await getAccounts()).filter((a) => a.token !== token);
    await keepAccounts(rest);
    await setToken(null);
    setApiToken(null);
    await clearCache();
    save('user', null);
    setUserState(null);
    if (rest[0]) await switchAccount(rest[0].id);               // вышли из одного — открывается следующий
  }, [keepAccounts, switchAccount]);

  useEffect(() => {
    onAuthLost(() => {
      setToken(null);
      setApiToken(null);
      setUserState(null);
      save('user', null);
    });
    (async () => {
      const savedLang = await load<Lang | null>('lang', null);
      applyLang(savedLang ?? deviceLang());
      setThemeModeState(await load<ThemeMode>('theme', 'system'));
      const savedCur = await load<string>('currency', '');
      setCurrencyState(savedCur);
      setApiCurrency(savedCur);
      setIntroSeen(await load<boolean>('intro_seen', false));
      const savedTabs = await load<TabKey[] | null>('tabs', null);
      if (savedTabs?.length) setTabsState(savedTabs.filter((k) => TAB_KEYS.includes(k)));
      setWallState(await load<Wall>('wall', {}));
      const p = await load<PrayerSettings | null>('prayer', null);
      if (p) {
        setPrayerState(p);
        prayerRef.current = p;
      }
      const token = await getToken();
      setApiToken(token);
      setAccountsState(await getAccounts());
      if (token) setUserState(await load<User | null>('user', null));
      setReady(true);
      await refreshConfig();
      if (token) {
        await refreshMe();
        registerPush();
      }
      const cur = p ?? DEFAULT_PRAYER;
      schedulePrayers(cur.place, cur.method, cur.asr, cur.alerts); // напоминания всегда на 7 дней вперёд
    })();
    onReachability(setOnline);
    const unsub = NetInfo.addEventListener((s) => {
      if (s.isConnected === false) setOnline(false);
      else if (s.isConnected) refreshConfig(); // сеть вернулась — проверим сервер (и снимем плашку)
    });
    return unsub;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // «в сети»: пока приложение открыто, раз в минуту сообщаем об этом серверу
  const uid = user?.id;
  useEffect(() => {
    if (!uid) return;
    const beat = () => { if (AppState.currentState === 'active') api('/ping/', { body: {} }).catch(() => {}); };
    const timer = setInterval(beat, 60000);
    const sub = AppState.addEventListener('change', (st) => { if (st === 'active') beat(); });
    return () => { clearInterval(timer); sub.remove(); };
  }, [uid]);

  const setLang = useCallback((l: Lang) => {
    applyLang(l);
    save('lang', l);
    refreshConfig();
    if (user) api('/me/', { method: 'PATCH', body: { language: l } }).catch(() => {});
  }, [refreshConfig, user]);

  // своя валюта: цены остаются в валюте автора, рядом — «≈» в выбранной
  const setCurrency = useCallback((code: string) => {
    setCurrencyState(code);
    setApiCurrency(code);
    save('currency', code);
    setLangTick((x) => x + 1);          // списки перечитают цены
    refreshConfig();
    if (user) api('/me/', { method: 'PATCH', body: { currency: code || 'auto' } }).catch(() => {});
  }, [refreshConfig, user]);

  const finishIntro = useCallback(() => { setIntroSeen(true); save('intro_seen', true); }, []);
  const setTabs = useCallback((keys: TabKey[]) => {
    const clean = keys.filter((k, i) => TAB_KEYS.includes(k) && keys.indexOf(k) === i).slice(0, TAB_SLOTS);
    const next = clean.length >= 2 ? clean : DEFAULT_TABS;
    setTabsState(next);
    save('tabs', next);
    if (user) api('/me/', { method: 'PATCH', body: { ui: { tabs_app: next } } }).catch(() => {});   // переживёт переустановку
  }, [user]);

  const setWall = useCallback((w: Wall) => {
    setWallState(w);
    save('wall', w);
  }, []);

  const setThemeMode = useCallback((m: ThemeMode) => {
    setThemeModeState(m);
    save('theme', m);
  }, []);

  const setPrayer = useCallback((part: Partial<PrayerSettings>) => {
    const next = { ...prayerRef.current, ...part };
    prayerRef.current = next;
    setPrayerState(next);
    save('prayer', next);
    schedulePrayers(next.place, next.method, next.asr, next.alerts);
  }, []);

  const signIn = useCallback(async (token: string, u: User) => {
    await setToken(token);
    setApiToken(token);
    await clearCache();
    setUserState(u);
    save('user', u);
    const others = (await getAccounts()).filter((a) => a.id !== u.id).slice(0, MAX_ACCOUNTS - 1);
    const list = [{ token, id: u.id, name: u.name, avatar: u.avatar ?? '' }, ...others];
    setAccountsState(list);
    setAccounts(list);
    if (u.language && ['ru', 'uz', 'en'].includes(u.language)) {
      applyLang(u.language as Lang);
      save('lang', u.language);
    } else {
      api('/me/', { method: 'PATCH', body: { language: lang } }).catch(() => {});
    }
    registerPush();
  }, [lang]);

  const dark = themeMode === 'dark' || (themeMode === 'system' && system === 'dark');
  const moduleOn = useCallback((key: string) => !!config?.modules.some((m) => m.key === key && m.status === 'on'), [config]);

  const value = useMemo<Ctx>(() => ({
    ready, lang, setLang, t: translate, themeMode, setThemeMode, dark, c: dark ? palettes.dark : palettes.light,
    config, refreshConfig, moduleOn, user, signIn, signOut, refreshMe, setUser: (u: User) => { setUserState(u); save('user', u); },
    accounts, switchAccount, canAddAccount: accounts.length < MAX_ACCOUNTS,
    prayer, setPrayer, online, langTick, currency, setCurrency, tabs, setTabs, wall, setWall, introSeen, finishIntro,
  }), [introSeen, finishIntro, tabs, setTabs, wall, setWall, ready, lang, setLang, themeMode, setThemeMode, dark, config, refreshConfig, moduleOn, user, signIn, signOut, accounts, switchAccount,
    refreshMe, prayer, setPrayer, online, langTick, currency, setCurrency]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): Ctx {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp вне AppProvider');
  return ctx;
}
