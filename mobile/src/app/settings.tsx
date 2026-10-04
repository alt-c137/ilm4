import Constants from 'expo-constants';
import { router } from 'expo-router';
import { useState } from 'react';

import { LANGS } from '@/lib/i18n';
import { openWeb } from '@/lib/links';
import { useApp } from '@/state/app';
import { Screen, SetGroup, SetRow, Sheet, Txt } from '@/ui/kit';

/**
 * «Настройки» — как в Telegram: всё, что можно настроить, в одном месте и по блокам.
 * Язык, оформление и валюта — строка с текущим значением, выбор — в списке снизу.
 */
export default function Settings() {
  const { t, lang, setLang, themeMode, setThemeMode, user, config, currency, setCurrency, moduleOn, accounts, switchAccount, canAddAccount } = useApp();
  const [pick, setPick] = useState<'lang' | 'theme' | 'currency' | 'accounts' | null>(null);
  const themes = [{ key: 'system' as const, label: t('Как в телефоне') }, { key: 'light' as const, label: t('Светлая') }, { key: 'dark' as const, label: t('Тёмная') }];
  const currencies = config?.currencies ?? [];
  const currencyName = currency ? `${currency}` : `${t('Авто')}${config?.currency ? ` · ${config.currency}` : ''}`;

  const sheet = pick === 'lang' ? { title: t('Язык'), items: LANGS.map((l) => ({ title: l.name, on: lang === l.code, onPress: () => setLang(l.code) })) }
    : pick === 'theme' ? { title: t('Тема'), items: themes.map((x) => ({ title: x.label, on: themeMode === x.key, onPress: () => setThemeMode(x.key) })) }
    : pick === 'currency' ? { title: t('Валюта'), items: [
      { title: `${t('Авто')}${config?.currency ? ` · ${config.currency}` : ''}`, subtitle: t('По стране, из которой вы зашли'), on: !currency, onPress: () => setCurrency('') },
      ...currencies.map((x) => ({ title: `${x.code} · ${x.name}`, on: currency === x.code, onPress: () => setCurrency(x.code) }))] }
    : pick === 'accounts' ? { title: t('Аккаунты'), items: [
      ...accounts.map((a) => ({ icon: 'person-circle-outline' as const, title: a.name, on: a.id === user?.id,
        subtitle: a.id === user?.id ? t('сейчас открыт') : undefined, onPress: () => { if (a.id !== user?.id) switchAccount(a.id); } })),
      ...(canAddAccount ? [{ icon: 'add-circle-outline' as const, title: t('Добавить аккаунт'), subtitle: t('Войти во второй аккаунт — этот останется на устройстве'),
        onPress: () => router.push('/login') }] : [])] }
    : { title: '', items: [] };

  return (
    <Screen title={t('Настройки')} back>
      {user ? (
        <SetGroup title={t('Аккаунт')}>
          <SetRow tint="#6d5efc" icon="person" title={t('Мой профиль')} subtitle={t('Имя, фото, @имя, о себе, соцсети')} onPress={() => router.push('/profile-edit')} />
          <SetRow tint="#8b5cf6" icon="people" title={t('Мои профили')} subtitle={t('Объявления, сообщества, никях')} onPress={() => router.push('/personas')} />
          <SetRow tint="#0ea5e9" icon="people-circle" title={t('Аккаунты')} value={accounts.length > 1 ? String(accounts.length) : undefined}
            subtitle={accounts.length > 1 ? undefined : t('Добавить и переключаться')} onPress={() => setPick('accounts')} />
        </SetGroup>
      ) : null}

      {user ? (
        <SetGroup>
          <SetRow tint="#22c55e" icon="lock-closed" title={t('Конфиденциальность')} subtitle={t('Номер, время в сети, закрытый профиль')} onPress={() => router.push('/privacy')} />
          <SetRow tint="#0ea5e9" icon="phone-portrait" title={t('Устройства')} subtitle={t('Активные сеансы, вход по QR-коду, двухшаговая защита')} onPress={() => router.push('/devices')} />
        </SetGroup>
      ) : null}

      <SetGroup title={t('Чаты и экран')}>
        <SetRow tint="#14b8a6" icon="image" title={t('Фон чата')} subtitle={t('Узор, цвет или своё фото')} onPress={() => router.push('/chat-look')} />
        {user && moduleOn('chat') ? <SetRow tint="#f59e0b" icon="folder-open" title={t('Папки с чатами')} subtitle={t('Свои вкладки над списком чатов')} onPress={() => router.push('/chat/folders')} /> : null}
        <SetRow tint="#16b3c4" icon="phone-portrait" title={t('Вид и рабочий стол')} subtitle={t('Дизайн как у Telegram, Авито, Instagram — и готовые наборы под задачи')} onPress={() => router.push('/look')} />
        <SetRow tint="#6d5efc" icon="apps" title={t('Нижние кнопки')} subtitle={t('Разделы внизу и стартовый экран')} onPress={() => router.push('/tabs-setup')} />
        <SetRow tint="#0ea5e9" icon="moon" title={t('Намаз и азан')} subtitle={t('Город, расчёт, напоминания')} onPress={() => router.push('/prayer-settings')} />
      </SetGroup>

      <SetGroup title={t('Оформление и язык')}>
        <SetRow tint="#475569" icon="contrast" title={t('Тема')} value={themes.find((x) => x.key === themeMode)?.label} onPress={() => setPick('theme')} />
        <SetRow tint="#3b82f6" icon="globe" title={t('Язык')} value={LANGS.find((l) => l.code === lang)?.name} onPress={() => setPick('lang')} />
        {currencies.length ? <SetRow tint="#10b981" icon="cash" title={t('Валюта')} value={currencyName} onPress={() => setPick('currency')} /> : null}
      </SetGroup>
      {currencies.length ? <Txt kind="small" style={{ paddingHorizontal: 6, marginTop: -6 }}>{t('Цены остаются в валюте автора, а рядом показываем «≈» в вашей.')}</Txt> : null}

      <SetGroup title={t('Помощь')}>
        <SetRow tint="#8b5cf6" icon="shield-checkmark" title={t('Правила')} onPress={() => openWeb('/rules/', false)} />
        <SetRow tint="#475569" icon="document-lock" title={t('Политика конфиденциальности')} onPress={() => openWeb('/privacy/', false)} />
      </SetGroup>

      {user ? (
        <SetGroup>
          <SetRow tint="#ef4444" icon="trash" title={t('Удалить аккаунт')} danger onPress={() => router.push('/account-delete')} />
        </SetGroup>
      ) : null}
      <Txt kind="small" style={{ textAlign: 'center' }}>ilm4 · {t('версия')} {Constants.expoConfig?.version ?? '1.0.0'}</Txt>

      <Sheet open={!!pick} onClose={() => setPick(null)} title={sheet.title} items={sheet.items} />
    </Screen>
  );
}
