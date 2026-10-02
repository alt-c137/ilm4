import * as Location from 'expo-location';
import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { distanceKm, qiblaBearing } from '@/lib/prayer';
import { useApp } from '@/state/app';
import { Card, Icon, Screen, Txt } from '@/ui/kit';

/** Кибла: направление на Каабу от севера + живой компас телефона. */
export default function Qibla() {
  const { c, t, prayer } = useApp();
  const [pos, setPos] = useState<{ lat: number; lon: number } | null>(prayer.place ? { lat: prayer.place.lat, lon: prayer.place.lon } : null);
  const [heading, setHeading] = useState<number | null>(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    let sub: Location.LocationSubscription | null = null;
    (async () => {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (!perm.granted) {
        setDenied(true);
        return;
      }
      try {
        const p = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
        setPos({ lat: p.coords.latitude, lon: p.coords.longitude });
      } catch {
        /* остаётся город из настроек */
      }
      try {
        sub = await Location.watchHeadingAsync((h) => setHeading(h.trueHeading >= 0 ? h.trueHeading : h.magHeading));
      } catch {
        /* нет компаса (эмулятор, веб) */
      }
    })();
    return () => sub?.remove();
  }, []);

  const bearing = pos ? qiblaBearing(pos.lat, pos.lon) : 0;
  const rot = heading === null ? bearing : bearing - heading;
  const aligned = heading !== null && Math.abs(((rot + 540) % 360) - 180) < 5;
  const km = pos ? Math.round(distanceKm(pos, { lat: 21.4225, lon: 39.8262 })) : 0;

  return (
    <Screen title={t('Кибла')} back>
      <View style={{ alignItems: 'center', paddingVertical: 20 }}>
        <View style={{ width: 280, height: 280, borderRadius: 140, borderWidth: 2, borderColor: aligned ? c.ok : c.line, backgroundColor: c.card, alignItems: 'center', justifyContent: 'center' }}>
          <View style={{ position: 'absolute', width: 276, height: 276, alignItems: 'center', transform: [{ rotate: `${-(heading ?? 0)}deg` }] }}>
            <Txt kind="h3" color={c.bad} style={{ marginTop: 8 }}>N</Txt>
          </View>
          <View style={{ transform: [{ rotate: `${rot}deg` }], alignItems: 'center', height: 240, justifyContent: 'flex-start' }}>
            <View style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: aligned ? c.ok : '#111', alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="cube" size={26} color="#e8c46a" />
            </View>
            <View style={{ width: 4, height: 90, backgroundColor: aligned ? c.ok : c.accent, borderRadius: 2 }} />
          </View>
          <View style={{ position: 'absolute', width: 14, height: 14, borderRadius: 7, backgroundColor: c.accent }} />
        </View>
      </View>
      <Card style={{ gap: 6, alignItems: 'center' }}>
        <Txt kind="h2">{Math.round(bearing)}°</Txt>
        <Txt kind="muted" style={{ textAlign: 'center' }}>
          {heading === null ? t('Направление от севера по часовой стрелке. Компас телефона недоступен — сверьтесь с обычным компасом.')
            : aligned ? t('Вы смотрите на Киблу') : t('Поворачивайте телефон, пока Кааба не окажется сверху')}
        </Txt>
        {km ? <Txt kind="small">{t('До Мекки ≈ {km} км', { km: km.toLocaleString('ru-RU') })}</Txt> : null}
        {denied ? <Txt kind="small" color={c.warn}>{t('Нет доступа к геолокации — считаем от выбранного города.')}</Txt> : null}
      </Card>
      <Txt kind="small" style={{ textAlign: 'center' }}>{t('Держите телефон горизонтально, вдали от металла и магнитов.')}</Txt>
    </Screen>
  );
}
