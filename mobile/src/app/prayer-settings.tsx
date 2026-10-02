import * as Location from 'expo-location';
import { useState } from 'react';
import { Alert, Switch, View } from 'react-native';

import { Notifications, PRAYER_NAMES } from '@/lib/notify';
import { FARD, type Method } from '@/lib/prayer';
import { useApp } from '@/state/app';
import { Button, Card, Chip, Divider, Field, Icon, Row, Screen, Section, Segmented, Txt } from '@/ui/kit';

const FALLBACK_METHODS: { key: Method; name: string }[] = [
  { key: 'Karachi', name: 'Университет Карачи — СНГ, Азия (по умолчанию)' },
  { key: 'MWL', name: 'Всемирная исламская лига — Европа, часть Азии' },
  { key: 'ISNA', name: 'ISNA — Северная Америка' },
  { key: 'Makkah', name: 'Умм аль-Кура — Саудовская Аравия' },
  { key: 'Egypt', name: 'Египетский орган — Африка, Левант' },
];

export default function PrayerSettings() {
  const { c, t, config, prayer, setPrayer } = useApp();
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const cities = (config?.prayer.cities ?? []).filter((x) => !q || x.name.toLowerCase().includes(q.toLowerCase()));
  const methods = config?.prayer.methods ?? FALLBACK_METHODS.map((m) => ({ ...m, name: t(m.name) }));

  const useGps = async () => {
    setBusy(true);
    try {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (!perm.granted) {
        Alert.alert(t('Нет доступа к геолокации'), t('Разрешите доступ в настройках телефона или выберите город из списка.'));
        return;
      }
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      let name = t('Моё место');
      try {
        const [g] = await Location.reverseGeocodeAsync(pos.coords);
        name = g?.city || g?.subregion || g?.region || name;
      } catch {
        /* без сети — без названия */
      }
      setPrayer({ place: { key: 'gps', gps: true, name, lat: pos.coords.latitude, lon: pos.coords.longitude, tz: null } });
    } catch {
      Alert.alert(t('Не удалось определить место'), t('Проверьте, что геолокация включена.'));
    } finally {
      setBusy(false);
    }
  };

  const alerts = prayer.alerts;
  const toggle = (k: string, v: boolean) => setPrayer({ alerts: { ...alerts, enabled: { ...alerts.enabled, [k]: v } } });

  return (
    <Screen title={t('Настройки намаза')} back>
      <Section title={t('Место')}>
        <Button title={prayer.place?.gps ? t('Обновить по GPS: {name}', { name: prayer.place.name }) : t('Определить по GPS')}
          icon="navigate" onPress={useGps} loading={busy} />
        <Field placeholder={t('Поиск города')} value={q} onChangeText={setQ} />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {cities.map((x) => (
            <Chip key={x.key} label={x.name} on={prayer.place?.key === x.key}
              onPress={() => setPrayer({ place: { key: x.key, name: x.name, lat: x.lat, lon: x.lon, tz: x.tz } })} />
          ))}
        </View>
      </Section>

      <Section title={t('Напоминания (азан)')}>
        {!Notifications ? (
          <Card soft><Txt kind="small" style={{ color: c.ink }}>{t('В тестовом Expo Go на Android напоминания не работают — это ограничение Expo Go. В установленном приложении ilm4 они работают.')}</Txt></Card>
        ) : null}
        <Card style={{ paddingVertical: 4 }}>
          {FARD.map((k, i) => (
            <View key={k}>
              {i ? <Divider /> : null}
              <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 10 }}>
                <Txt kind="h3" style={{ flex: 1, fontWeight: '600' }}>{t(PRAYER_NAMES[k])}</Txt>
                <Switch value={!!alerts.enabled[k]} onValueChange={(v) => toggle(k, v)} trackColor={{ true: c.accent, false: c.line }} />
              </View>
            </View>
          ))}
        </Card>
        <Txt kind="small">{t('Напомнить заранее')}</Txt>
        <Segmented value={String(alerts.before)} onChange={(v) => setPrayer({ alerts: { ...alerts, before: Number(v) } })}
          options={['0', '5', '10', '15', '30'].map((m) => ({ key: m, label: m === '0' ? t('Вовремя') : t('{m} мин', { m }) }))} />
      </Section>

      <Section title={t('Метод расчёта')}>
        <Card style={{ paddingVertical: 4 }}>
          {methods.map((m, i) => (
            <View key={m.key}>
              {i ? <Divider /> : null}
              <Row title={m.name} onPress={() => setPrayer({ method: m.key })}
                right={prayer.method === m.key ? <Icon name="checkmark-circle" color={c.accent} /> : <Icon name="ellipse-outline" color={c.line} />} />
            </View>
          ))}
        </Card>
      </Section>

      <Section title={t('Время Асра')}>
        <Segmented value={prayer.asr} onChange={(v) => setPrayer({ asr: v })}
          options={[{ key: 'standard', label: t('Стандарт (3 мазхаба)') }, { key: 'hanafi', label: t('Ханафитский') }]} />
        <Txt kind="small">{t('По ханафитскому мазхабу Аср наступает позже — когда тень вдвое длиннее предмета.')}</Txt>
      </Section>
    </Screen>
  );
}
