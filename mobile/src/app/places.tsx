import * as Location from 'expo-location';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, View } from 'react-native';

import { api } from '@/lib/api';
import { distanceKm } from '@/lib/prayer';
import { load, save } from '@/lib/storage';
import { useApp } from '@/state/app';
import { Button, Card, Chip, Empty, Icon, Loading, Screen, Segmented, Txt } from '@/ui/kit';
import { PlacesMap } from '@/ui/map';

type P = { id: number; name: string; category: string; category_name: string; lat: number; lon: number; verified: boolean; km?: number };

/** Халяль-места рядом: по GPS или от города из настроек намаза, с расстоянием. */
export default function Places() {
  const { c, t, prayer, user } = useApp();
  const [items, setItems] = useState<P[] | null>(null);
  const [cat, setCat] = useState('');
  const [radius, setRadius] = useState(10);
  const [where, setWhere] = useState<{ lat: number; lon: number } | null>(prayer.place ? { lat: prayer.place.lat, lon: prayer.place.lon } : null);
  const [error, setError] = useState('');
  const [mode, setMode] = useState<'list' | 'map'>('map');
  const [me, setMe] = useState<{ lat: number; lon: number } | null>(null);
  const [mapItems, setMapItems] = useState<P[]>([]);

  const locate = async () => {
    const perm = await Location.requestForegroundPermissionsAsync();
    if (!perm.granted) return;
    try {
      const p = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      setWhere({ lat: p.coords.latitude, lon: p.coords.longitude });
      setMe({ lat: p.coords.latitude, lon: p.coords.longitude });
    } catch {
      /* остаётся город */
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- определить место при открытии
    locate();
  }, []);

  useEffect(() => {
    if (!where) return;
    const d = radius / 111;
    const bbox = [where.lat - d, where.lon - d * 1.5, where.lat + d, where.lon + d * 1.5].map((x) => x.toFixed(4)).join(',');
    const key = `places:${bbox}:${cat}`;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- сброс списка при смене радиуса/категории
    setItems(null);
    api<{ items: P[] }>(`/places/map/?bbox=${bbox}&category=${cat}`)
      .then((r) => { save(key, r.items); return r.items; })
      .catch(async (e) => { setError(e.message); return load<P[]>(key, []); })
      .then((list) => setItems(list.map((x) => ({ ...x, km: distanceKm(where, x) })).filter((x) => x.km! <= radius).sort((a, b) => a.km! - b.km!)));
  }, [where, radius, cat]);

  // карта: метки видимой области (двигаешь карту — подгружаются новые)
  const onMove = (b: [number, number, number, number]) => {
    const bbox = b.map((x) => x.toFixed(4)).join(',');
    api<{ items: P[] }>(`/places/map/?bbox=${bbox}&category=${cat}`).then((r) => setMapItems(r.items)).catch(() => {});
  };
  const markers = (mapItems.length ? mapItems : items ?? []).map((p) => ({ id: p.id, lat: p.lat, lon: p.lon, title: p.name, sub: p.category_name, mosque: p.category === 'mosque' }));

  const cats = Array.from(new Map((items ?? []).map((x) => [x.category, x.category_name])).entries());

  return (
    <Screen title={t('Халяль-места рядом')} back right={
      <View style={{ flexDirection: 'row', gap: 16 }}>
        <Pressable onPress={() => (user ? router.push('/publish/places') : router.push('/login'))} hitSlop={8}><Icon name="add-circle-outline" color={c.accent} /></Pressable>
        <Pressable onPress={() => router.push('/pubs/places')} hitSlop={8}><Icon name="list" color={c.accent} /></Pressable>
      </View>}>
      <Segmented value={mode} onChange={setMode} options={[{ key: 'map', label: t('Карта') }, { key: 'list', label: t('Списком') }]} />
      {mode === 'map' && where ? (
        <View style={{ height: 460 }}>
          <PlacesMap center={where} me={me} markers={markers} onSelect={(id) => router.push(`/pub/places/${id}`)} onMove={onMove} />
        </View>
      ) : null}
      {mode === 'list' ? <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
        {[3, 10, 30, 100].map((r) => <Chip key={r} label={t('{n} км', { n: r })} on={radius === r} onPress={() => setRadius(r)} />)}
      </ScrollView> : null}
      {cats.length > 1 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          <Chip label={t('Все')} on={!cat} onPress={() => setCat('')} />
          {cats.map(([k, n]) => <Chip key={k} label={n} on={cat === k} onPress={() => setCat(k)} />)}
        </ScrollView>
      ) : null}
      {!where ? <Button title={t('Определить по GPS')} icon="navigate" onPress={locate} /> : null}
      {mode === 'map' ? null : items === null ? <Loading /> : !items.length ? (
        <Empty icon="location-outline" title={t('Рядом пока ничего нет')} text={error || t('Увеличьте радиус или добавьте место на сайте.')} />
      ) : items.map((p) => (
        <Card key={p.id} onPress={() => router.push(`/pub/places/${p.id}`)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <View style={{ width: 44, height: 44, borderRadius: 14, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
            <Icon name={p.category === 'mosque' ? 'moon' : 'restaurant'} size={20} color={c.accent} />
          </View>
          <View style={{ flex: 1 }}>
            <Txt kind="h3" numberOfLines={1}>{p.name}{p.verified ? ' ✓' : ''}</Txt>
            <Txt kind="small">{p.category_name}</Txt>
          </View>
          <Txt kind="h3" color={c.accentD}>{p.km! < 1 ? t('{m} м', { m: Math.round(p.km! * 1000) }) : t('{n} км', { n: p.km!.toFixed(1) })}</Txt>
        </Card>
      ))}
    </Screen>
  );
}
