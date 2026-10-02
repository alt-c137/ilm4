import { View } from 'react-native';

import { shortDate } from '@/lib/hijri';
import { openWeb } from '@/lib/links';
import { useApp } from '@/state/app';
import { Button, Card, Empty, ErrorBox, Loading, Screen, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

export default function Wallet() {
  const { c, t } = useApp();
  const { data, loading, error, reload } = useFetch<any>('/wallet/');
  return (
    <Screen title={t('Кошелёк')} back onRefresh={reload} refreshing={loading && !!data}>
      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : (
        <>
          <Card style={{ gap: 12, backgroundColor: c.accent }}>
            <Txt kind="label" color="rgba(255,255,255,0.8)">{t('Баланс')}</Txt>
            <Txt style={{ fontSize: 34, fontWeight: '800' }} color="#fff">{data.balance.toLocaleString('ru-RU')} {t('сум')}</Txt>
            <Button title={t('Пополнить')} icon="add-circle" kind="soft" onPress={() => openWeb('/wallet/topup/')} />
          </Card>
          <Txt kind="small">{t('Оплата открывается на защищённой странице ilm4: карты Uzcard/Humo, Visa/Mastercard, криптовалюта, Telegram Stars.')}</Txt>
          {!data.items.length ? <Empty title={t('Операций пока нет')} /> : data.items.map((x: any) => (
            <Card key={x.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Txt kind="h3" style={{ fontWeight: '600' }}>{x.kind}</Txt>
                <Txt kind="small">{x.note ? `${x.note} · ` : ''}{shortDate(x.created_at)}</Txt>
              </View>
              <Txt kind="h3" color={x.amount < 0 ? c.bad : c.ok}>{x.amount > 0 ? '+' : ''}{x.amount.toLocaleString('ru-RU')}</Txt>
            </Card>
          ))}
        </>
      )}
    </Screen>
  );
}
