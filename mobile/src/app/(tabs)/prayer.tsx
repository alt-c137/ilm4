import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, View } from 'react-native';

import { gregText, hijriText } from '@/lib/hijri';
import { PRAYER_NAMES } from '@/lib/notify';
import { PRAYER_KEYS } from '@/lib/prayer';
import { load, save } from '@/lib/storage';
import { useApp } from '@/state/app';
import { Button, Card, Icon, Screen, Txt } from '@/ui/kit';
import { fmtLeft, usePrayerNow } from '@/ui/usePrayer';

type Weather = { temp: number; code: number; tmax: number; tmin: number; at: number };

const WX: [number[], string, string][] = [
  [[0], 'Ясно', 'sunny-outline'], [[1, 2], 'Облачно', 'partly-sunny-outline'], [[3], 'Пасмурно', 'cloud-outline'],
  [[45, 48], 'Туман', 'cloudy-outline'], [[51, 53, 55, 56, 57, 61, 63, 66], 'Дождь', 'rainy-outline'],
  [[65, 67, 80, 81, 82], 'Ливень', 'rainy-outline'], [[71, 73, 75, 77, 85, 86], 'Снег', 'snow-outline'],
  [[95, 96, 99], 'Гроза', 'thunderstorm-outline'],
];

/** Погода — бесплатный Open-Meteo без ключа, кеш на 30 минут (офлайн — последняя известная). */
function useWeather(lat?: number, lon?: number) {
  const [w, setW] = useState<Weather | null>(null);
  useEffect(() => {
    if (lat === undefined || lon === undefined) return;
    const key = `wx:${lat.toFixed(2)},${lon.toFixed(2)}`;
    let alive = true;
    (async () => {
      const old = await load<Weather | null>(key, null);
      if (old && alive) setW(old);
      if (old && Date.now() - old.at < 30 * 60000) return;
      try {
        const r = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=1`);
        const j = await r.json();
        const v = { temp: Math.round(j.current.temperature_2m), code: j.current.weather_code, tmax: Math.round(j.daily.temperature_2m_max[0]), tmin: Math.round(j.daily.temperature_2m_min[0]), at: Date.now() };
        if (alive) setW(v);
        save(key, v);
      } catch {
        /* без сети — остаётся сохранённая */
      }
    })();
    return () => {
      alive = false;
    };
  }, [lat, lon]);
  return w;
}

export default function PrayerScreen() {
  const { c, t, prayer } = useApp();
  const p = usePrayerNow();
  const place = prayer.place;
  const w = useWeather(place?.lat, place?.lon);
  const wx = w ? WX.find(([codes]) => codes.includes(w.code)) : null;
  const now = new Date();

  return (
    <Screen title={t('Время намаза')} right={
      <Pressable onPress={() => router.push('/prayer-settings')} hitSlop={10}><Icon name="options-outline" size={24} color={c.accent} /></Pressable>}>
      <Pressable onPress={() => router.push('/prayer-settings')}>
        <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <Icon name={place?.gps ? 'navigate' : 'location'} color={c.accent} />
          <View style={{ flex: 1 }}>
            <Txt kind="h3">{place?.name ?? t('Выберите город')}</Txt>
            <Txt kind="small">{gregText(now)} · {hijriText(now)}</Txt>
          </View>
          {w && wx ? (
            <View style={{ alignItems: 'flex-end' }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                <Icon name={wx[2] as any} size={20} color={c.accent} />
                <Txt kind="h3">{w.temp}°</Txt>
              </View>
              <Txt kind="small">{t(wx[1])} · {w.tmin}…{w.tmax}°</Txt>
            </View>
          ) : null}
        </Card>
      </Pressable>

      {p ? (
        <>
          <View style={{ alignItems: 'center', paddingVertical: 8 }}>
            <Txt kind="label">{t('До намаза {name}', { name: t(PRAYER_NAMES[p.next.key]) })}</Txt>
            <Txt style={{ fontSize: 46, lineHeight: 56, marginTop: 4, fontWeight: '800', fontVariant: ['tabular-nums'], color: c.accent }}>{fmtLeft(p.left)}</Txt>
          </View>
          <Card style={{ paddingVertical: 6 }}>
            {PRAYER_KEYS.map((k) => {
              const cur = p.current === k;
              const on = prayer.alerts.enabled[k as keyof typeof prayer.alerts.enabled];
              return (
                <View key={k} style={{
                  flexDirection: 'row', alignItems: 'center', paddingVertical: 14, paddingHorizontal: 12, borderRadius: 16,
                  backgroundColor: cur ? c.accentSoft : 'transparent',
                }}>
                  <Txt kind="h3" style={{ flex: 1, fontSize: 17 }} color={cur ? c.accentD : k === 'sunrise' ? c.inkSoft : c.ink}>{t(PRAYER_NAMES[k])}</Txt>
                  {k !== 'sunrise' ? <Icon name={on ? 'notifications' : 'notifications-off-outline'} size={16} color={on ? c.accent : c.inkSoft} style={{ marginRight: 12 }} /> : null}
                  <Txt style={{ fontSize: 20, fontWeight: '800', fontVariant: ['tabular-nums'] }} color={cur ? c.accentD : c.ink}>{p.today.times[k]}</Txt>
                </View>
              );
            })}
          </Card>
        </>
      ) : (
        <Button title={t('Выбрать город')} icon="location" onPress={() => router.push('/prayer-settings')} />
      )}

      <View style={{ flexDirection: 'row', gap: 10 }}>
        <Card style={{ flex: 1, alignItems: 'center', gap: 6 }} onPress={() => router.push('/qibla')}>
          <Icon name="compass" size={28} color={c.accent} />
          <Txt kind="h3" style={{ textAlign: 'center' }}>{t('Кибла')}</Txt>
        </Card>
        <Card style={{ flex: 1, alignItems: 'center', gap: 6 }} onPress={() => router.push('/prayer-month')}>
          <Icon name="calendar" size={28} color={c.accent} />
          <Txt kind="h3" style={{ textAlign: 'center' }}>{t('На месяц')}</Txt>
        </Card>
        <Card style={{ flex: 1, alignItems: 'center', gap: 6 }} onPress={() => router.push('/prayer-settings')}>
          <Icon name="notifications" size={28} color={c.accent} />
          <Txt kind="h3" style={{ textAlign: 'center' }}>{t('Азан')}</Txt>
        </Card>
      </View>
      <Txt kind="small" style={{ textAlign: 'center' }}>{t('Время считается прямо на телефоне — работает без интернета.')}</Txt>
    </Screen>
  );
}
