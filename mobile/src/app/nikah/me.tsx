import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Linking, Share, Switch, View } from 'react-native';

import { api } from '@/lib/api';
import { openWeb } from '@/lib/links';
import { useApp } from '@/state/app';
import { Card, Divider, ErrorBox, Loading, Row, Screen, Txt } from '@/ui/kit';
import { KV, ProfileHead } from '@/ui/nikah';
import { useFetch } from '@/ui/useFetch';

export default function NikahMe() {
  const { c, t, config } = useApp();
  const { data, loading, error, reload } = useFetch<any>('/nikah/state/');
  const [busy, setBusy] = useState(false);
  useFocusEffect(useCallback(() => { reload(true); }, [reload]));
  if (!data?.profile) return <Screen back title={t('Моя анкета')}>{loading ? <Loading /> : <ErrorBox error={error?.message ?? t('Анкеты нет')} onRetry={reload} />}</Screen>;
  const p = data.profile;
  const nk = config?.features.nikah;
  const status = { pending: t('На проверке'), approved: t('Опубликована'), rejected: t('Отклонена') }[p.status as string] ?? p.status;

  const premium = () => Alert.alert(t('Премиум'), t('{p} сум на {d} дней: без дневного лимита, фильтр «в сети», бесплатный возврат отклонённых.', { p: nk?.premium_price?.toLocaleString('ru-RU') ?? '', d: nk?.premium_days ?? '' }), [
    { text: t('Отмена'), style: 'cancel' },
    { text: t('Подключить'), onPress: async () => {
      setBusy(true);
      try {
        await api('/nikah/premium/', { body: {} });
        Alert.alert(t('Премиум подключён. БаракаЛлаху фик!'));
        reload();
      } catch (e: any) {
        Alert.alert(e.message, undefined, e.code === 'money' ? [{ text: t('Пополнить'), onPress: () => openWeb('/wallet/topup/') }, { text: 'OK' }] : undefined);
      } finally {
        setBusy(false);
      }
    } },
  ]);
  const pause = async (active: boolean) => {
    await api('/nikah/pause/', { body: { pause: !active } }).catch((e) => Alert.alert(e.message));
    reload();
  };

  return (
    <Screen back title={t('Моя анкета')} onRefresh={reload} refreshing={loading}>
      <Card style={{ gap: 12 }}>
        <ProfileHead p={p} />
        <KV items={[[t('Статус'), status], [t('Премиум'), p.premium_until ? t('до {d}', { d: new Date(p.premium_until).toLocaleDateString() }) : t('нет')],
          [t('Баланс'), `${data.balance.toLocaleString('ru-RU')} ${t('сум')}`], [t('Анкет сегодня'), data.left === null ? '∞' : `${data.left} / ${data.limit}`]]} />
      </Card>
      <Card style={{ paddingVertical: 4 }}>
        <Row icon="create-outline" title={t('Изменить анкету')} subtitle={t('Тексты и фото снова проверит модератор')} onPress={() => router.push('/nikah/form')} />
        <Divider />
        <Row icon="pause-circle-outline" title={t('Анкета видна другим')} right={<Switch value={p.active} onValueChange={pause} trackColor={{ true: c.accent, false: c.line }} />} />
        <Divider />
        {nk?.premium ? <><Row icon="diamond-outline" title={t('Премиум')} subtitle={p.premium_until ? t('Продлить') : t('Без лимитов')} onPress={premium} /><Divider /></> : null}
        <Row icon="videocam-outline" title={t('Верификация')} subtitle={p.verified ? t('Пройдена ✓') : t('Видео-кружок модератору в Telegram')}
          onPress={p.verified ? undefined : () => (config?.bot ? Linking.openURL(`https://t.me/${config.bot}?start=verify`) : openWeb('/nikah/settings/'))} />
        <Divider />
        <Row icon="share-social-outline" title={t('Пригласить друга')} subtitle={t('Бонус к премиуму за каждую анкету по вашей ссылке')}
          onPress={() => Share.share({ message: `${t('Никях ilm4 — знакомство для брака по Корану и Сунне')}\n${data.invite}` })} />
        <Divider />
        <Row icon="people-outline" title={t('Свидетель (махрам)')} subtitle={t('Пригласить отца или брата в переписку')} onPress={() => openWeb('/nikah/settings/')} />
      </Card>
      {busy ? <Loading /> : null}
      <View style={{ height: 8 }} />
      <Txt kind="small" style={{ textAlign: 'center' }}>{t('Закрытые ответы о религии видит только модератор.')}</Txt>
    </Screen>
  );
}
