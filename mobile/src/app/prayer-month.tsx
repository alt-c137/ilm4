import { View } from 'react-native';

import { hijriText } from '@/lib/hijri';
import { PRAYER_NAMES } from '@/lib/notify';
import { dayTimes, PRAYER_KEYS } from '@/lib/prayer';
import { useApp } from '@/state/app';
import { Card, Empty, Screen, Txt } from '@/ui/kit';

export default function PrayerMonth() {
  const { c, t, prayer } = useApp();
  const place = prayer.place;
  if (!place) return <Screen title={t('На месяц')} back><Empty title={t('Выберите город')} /></Screen>;
  const now = new Date();
  const days = Array.from({ length: 30 }, (_, i) => dayTimes(place, new Date(now.getTime() + i * 86400000), prayer.method, prayer.asr));
  return (
    <Screen title={t('Расписание: {name}', { name: place.name })} back>
      <Card style={{ padding: 8 }}>
        <View style={{ flexDirection: 'row', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: c.line }}>
          <Txt kind="small" style={{ width: 54, fontWeight: '700' }}>{t('Дата')}</Txt>
          {PRAYER_KEYS.map((k) => <Txt key={k} kind="small" style={{ flex: 1, textAlign: 'center', fontWeight: '700' }} numberOfLines={1}>{t(PRAYER_NAMES[k])}</Txt>)}
        </View>
        {days.map((d, i) => {
          const local = new Date(now.getTime() + i * 86400000);
          const fri = local.getDay() === 5;
          return (
            <View key={i} style={{ flexDirection: 'row', paddingVertical: 9, backgroundColor: i === 0 ? c.accentSoft : fri ? c.card2 : 'transparent', borderRadius: 10 }}>
              <View style={{ width: 54 }}>
                <Txt kind="h3" style={{ fontSize: 14 }}>{`${String(local.getDate()).padStart(2, '0')}.${String(local.getMonth() + 1).padStart(2, '0')}`}</Txt>
                <Txt kind="small" style={{ fontSize: 10 }} numberOfLines={1}>{hijriText(local).split(' ').slice(0, 2).join(' ')}</Txt>
              </View>
              {PRAYER_KEYS.map((k) => <Txt key={k} style={{ flex: 1, textAlign: 'center', fontSize: 14, fontVariant: ['tabular-nums'], color: k === 'sunrise' ? c.inkSoft : c.ink }}>{d.times[k]}</Txt>)}
            </View>
          );
        })}
      </Card>
    </Screen>
  );
}
