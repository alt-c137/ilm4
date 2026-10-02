import { Image } from 'expo-image';
import { useScreenshotListener } from 'expo-screen-capture';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, AppState, Platform, Pressable, View } from 'react-native';

import { api, API_URL, authHeaders } from '@/lib/api';
import { openWeb } from '@/lib/links';
import { useApp } from '@/state/app';
import { Button, Card, ErrorBox, Icon, Loading, Screen, Txt } from '@/ui/kit';
import { ProfileHead, type NkProfile } from '@/ui/nikah';
import { useFetch } from '@/ui/useFetch';
import { fmtLeft } from '@/ui/usePrayer';

type M = {
  id: number; stage: 'photos' | 'chat' | 'closed'; stage_name: string; side: 'sister' | 'brother'; turn: string | null; opened: boolean;
  my_ok: boolean | null; their_ok: boolean | null; seconds: number; minutes: number; price: number; chat_paid: boolean;
  thread_id: number | null; partner: NkProfile; balance: number | null;
};

/** Скриншот запрещён системой; если телефон всё же сообщил о нём — предупреждаем. */
function ScreenshotWarn() {
  const { t } = useApp();
  useScreenshotListener(() => Alert.alert(t('Скриншоты запрещены'), t('Вы обещали не сохранять чужие фото. Нарушение — блокировка.')));
  return null;
}

export default function NikahMatch() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { c, t } = useApp();
  const { data: m, setData, loading, error, reload } = useFetch<M>(`/nikah/match/${id}/`);
  const [oath, setOath] = useState(false);
  const [busy, setBusy] = useState(false);
  const [left, setLeft] = useState(0);
  const [hidden, setHidden] = useState(false);

  // скриншот запрещён системой; если телефон всё же сообщил о нём — предупреждаем

  useEffect(() => {
    if (!m) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- таймер начинается с оставшихся секунд с сервера
    setLeft(m.seconds);
    const timer = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(timer);
  }, [m]);

  // свернули приложение — фото скрывается
  useEffect(() => {
    const sub = AppState.addEventListener('change', (s) => setHidden(s !== 'active'));
    return () => sub.remove();
  }, []);

  if (!m) return <Screen back title="">{loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />}</Screen>;

  const act = async (path: string, body: object) => {
    setBusy(true);
    try {
      setData(await api(`/nikah/match/${m.id}/${path}/`, { body }));
    } catch (e: any) {
      Alert.alert(e.message, undefined, e.code === 'money' ? [{ text: t('Пополнить'), onPress: () => openWeb('/wallet/topup/') }, { text: 'OK' }] : undefined);
    } finally {
      setBusy(false);
    }
  };

  const myTurn = m.turn === m.side;
  const showPhoto = m.stage === 'photos' && myTurn && m.opened && left > 0 && m.partner.has_photo !== false;

  return (
    <Screen back title={t('Взаимная симпатия')} onRefresh={reload} refreshing={loading}>
      {Platform.OS !== 'web' ? <ScreenshotWarn /> : null}
      <Card onPress={() => router.push(`/nikah/${m.partner.id}`)}><ProfileHead p={m.partner} /></Card>

      {m.stage === 'closed' ? (
        <Card style={{ alignItems: 'center', gap: 8 }}>
          <Icon name="leaf-outline" size={36} color={c.inkSoft} />
          <Txt kind="h3" style={{ textAlign: 'center' }}>{t('Не сложилось')}</Txt>
          <Txt kind="muted" style={{ textAlign: 'center' }}>{t('Аллах предопределил лучшее. Продолжайте поиск — ин шаа Аллах, найдёте свою судьбу.')}</Txt>
        </Card>
      ) : m.stage === 'chat' ? (
        <Card style={{ gap: 10 }}>
          <Txt kind="h3">{t('Оба согласны — БаракаЛлаху фикум!')}</Txt>
          {m.thread_id ? (
            <Button title={t('Открыть чат')} icon="chatbubbles" onPress={() => router.push(`/chat/${m.thread_id}`)} />
          ) : m.side === 'brother' && m.price && !m.chat_paid ? (
            <>
              <Txt kind="muted">{t('Открытие чата — {p} сум. Баланс: {b} сум.', { p: m.price.toLocaleString('ru-RU'), b: (m.balance ?? 0).toLocaleString('ru-RU') })}</Txt>
              <Button title={t('Оплатить и открыть чат')} onPress={() => act('pay', {})} loading={busy} />
            </>
          ) : <Txt kind="muted">{t('Ждём, пока брат откроет чат.')}</Txt>}
        </Card>
      ) : !myTurn ? (
        <Card style={{ gap: 6 }}>
          <Txt kind="h3">{m.my_ok ? t('Вы согласились. Ждём решения второй стороны.') : m.side === 'brother' ? t('Сестра смотрит ваше фото первой') : t('Ждём ответа брата')}</Txt>
          <Txt kind="muted">{t('Мы пришлём уведомление, когда настанет ваша очередь.')}</Txt>
        </Card>
      ) : !m.opened ? (
        <Card style={{ gap: 12 }}>
          <Txt kind="h3">{t('Ваша очередь посмотреть фото')}</Txt>
          <Txt kind="muted">{t('Фото откроется один раз на {m} минут, с водяным знаком. Не решите за это время — это считается отказом.', { m: m.minutes })}</Txt>
          <Pressable onPress={() => setOath(!oath)} style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start' }}>
            <Icon name={oath ? 'checkbox' : 'square-outline'} color={c.accent} />
            <Txt style={{ flex: 1 }}>{t('Обещаю перед Аллахом не сохранять, не фотографировать и не пересылать это фото.')}</Txt>
          </Pressable>
          <Button title={t('Открыть фото')} icon="eye" disabled={!oath} loading={busy} onPress={() => act('open', { oath: 1 })} />
        </Card>
      ) : (
        <Card style={{ gap: 12 }}>
          {showPhoto && !hidden ? (
            <Image source={{ uri: `${API_URL}/api/v1/nikah/match/${m.id}/photo/`, headers: authHeaders() }}
              style={{ width: '100%', aspectRatio: 3 / 4, borderRadius: 18, backgroundColor: c.card2 }} contentFit="cover" cachePolicy="none" />
          ) : (
            <View style={{ aspectRatio: 3 / 4, borderRadius: 18, backgroundColor: c.card2, alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="eye-off-outline" size={40} color={c.inkSoft} />
              <Txt kind="muted">{left > 0 ? t('Фото скрыто') : t('Время вышло')}</Txt>
            </View>
          )}
          {left > 0 ? <Txt kind="h3" style={{ textAlign: 'center' }} color={left < 60 ? c.bad : c.accent}>{t('Осталось {time}', { time: fmtLeft(left) })}</Txt> : null}
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <Button kind="ghost" color={c.bad} title={t('Нет')} icon="close" style={{ flex: 1 }} onPress={() => act('decide', { ok: 0 })} loading={busy} />
            <Button title={t('Да, продолжить')} icon="heart" style={{ flex: 1.6 }} onPress={() => act('decide', { ok: 1 })} loading={busy} />
          </View>
        </Card>
      )}
      <Txt kind="small" style={{ textAlign: 'center' }}>{t('Сестра смотрит фото первой. Если она согласна — очередь брата. Если оба «да» — открывается чат.')}</Txt>
    </Screen>
  );
}
