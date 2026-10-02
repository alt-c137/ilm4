/**
 * Подтверждение номера через Telegram-бота (бесплатно, без SMS).
 * Сервер требует его перед подачей объявлений и входом в никях: один номер — один аккаунт,
 * поэтому боты не спамят, а лимит никяха не обойти новым аккаунтом.
 */
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Alert, Linking, Pressable, View } from 'react-native';

import { api } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, Icon, Screen, Txt } from '@/ui/kit';

export default function VerifyPhone() {
  const { c, t, refreshMe } = useApp();
  const { why } = useLocalSearchParams<{ why?: string }>();
  const [waiting, setWaiting] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState('');
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (poll.current) clearInterval(poll.current); }, []);

  const start = async () => {
    setError('');
    try {
      const r = await api('/auth/phone/', { body: {} });
      if (r.verified) {
        await refreshMe();
        router.back();
        return;
      }
      setWaiting(true);
      await Linking.openURL(r.url);
      if (poll.current) clearInterval(poll.current);
      const started = Date.now();
      poll.current = setInterval(async () => {
        if (Date.now() - started > 15 * 60000) {
          clearInterval(poll.current!);
          setWaiting(false);
          return;
        }
        try {
          const s = await api(`/auth/phone/status/?nonce=${encodeURIComponent(r.nonce)}`);
          if (s.verified) {
            clearInterval(poll.current!);
            setWaiting(false);
            setDone(s.phone || '');
            await refreshMe();
          } else if (s.error) setError(s.error);
        } catch {
          // нет сети — попробуем ещё раз через 2 секунды
        }
      }, 2000);
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };

  return (
    <Screen title={t('Подтверждение номера')} right={
      <Pressable onPress={() => router.back()} hitSlop={10}><Icon name="close" size={26} color={c.inkSoft} /></Pressable>}>
      <View style={{ alignItems: 'center', gap: 10, paddingVertical: 8 }}>
        <View style={{ width: 72, height: 72, borderRadius: 22, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
          <Icon name={done ? 'checkmark-circle' : 'phone-portrait-outline'} size={38} color={c.accent} />
        </View>
        <Txt kind="h2" style={{ textAlign: 'center' }}>{done ? t('Номер подтверждён') : t('Подтвердите номер телефона')}</Txt>
      </View>
      {done ? (
        <>
          <Txt kind="muted" style={{ textAlign: 'center' }}>{done} — {t('можно подавать объявления и пользоваться никяхом.')}</Txt>
          <Button title={t('Продолжить')} onPress={() => router.back()} />
        </>
      ) : (
        <>
          <Txt kind="muted">
            {why === 'nikah'
              ? t('Никях открыт только людям с подтверждённым номером: один номер — одна анкета. Так в ленте нет ботов и фейков.')
              : t('Публиковать можно только с подтверждённым номером: один номер — один аккаунт. Так на ilm4 нет спама и ботов.')}
            {' '}{t('Смотреть объявления можно и без этого.')}
          </Txt>
          <Card style={{ gap: 8 }}>
            <Txt>1. {t('Нажмите кнопку ниже — откроется наш бот в Telegram.')}</Txt>
            <Txt>2. {t('В боте нажмите «📱 Отправить мой номер».')}</Txt>
            <Txt>3. {t('Вернитесь сюда — страница откроется сама.')}</Txt>
          </Card>
          <Button title={waiting ? t('Ждём подтверждения из Telegram…') : t('Подтвердить через Telegram')} icon="paper-plane"
            onPress={start} style={{ backgroundColor: '#229ED9' }} />
          {error ? <Txt color={c.bad}>{error}</Txt> : null}
          <Txt kind="small" style={{ textAlign: 'center' }}>{t('Номер не видят другие люди.')}</Txt>
        </>
      )}
    </Screen>
  );
}
