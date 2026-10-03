import { Image } from 'expo-image';
import * as Location from 'expo-location';
import { router } from 'expo-router';
import { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { FlatList, Linking, Platform, Pressable, ScrollView, TextInput, View } from 'react-native';
import Animated, { FadeInDown, FadeOut } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api } from '@/lib/api';
import { distanceKm } from '@/lib/prayer';
import { load, save } from '@/lib/storage';
import { useApp } from '@/state/app';
import { Icon, OfflineBar, TabMode, Txt } from '@/ui/kit';
import { PlaceIcon, PlacesMap } from '@/ui/map';

type P = { id: number; name: string; category: string; category_name: string; lat: number; lon: number; verified: boolean; icon?: string;
  address?: string; city?: string; phone?: string; verif?: string; verif_label?: string; brief?: string; photo?: string };
type Cat = { key: string; name: string; icon: string };

/** Халяль-места — как в навигаторах: карта на весь экран, поиск и категории поверх, «где я», список рядом и карточка с маршрутом. */
export default function Places() {
  const { c, t, prayer, user } = useApp();
  const inTab = useContext(TabMode);
  const [where, setWhere] = useState<{ lat: number; lon: number } | null>(prayer.place ? { lat: prayer.place.lat, lon: prayer.place.lon } : null);
  const [me, setMe] = useState<{ lat: number; lon: number } | null>(null);
  const [items, setItems] = useState<P[]>([]);
  const [cats, setCats] = useState<Cat[]>([]);
  const [cat, setCat] = useState('');
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [verified, setVerified] = useState(false);
  const [sel, setSel] = useState<P | null>(null);
  const [listOpen, setListOpen] = useState(false);
  const bbox = useRef<string>('');

  const locate = useCallback(async () => {
    const perm = await Location.requestForegroundPermissionsAsync();
    if (!perm.granted) return;
    try {
      const p = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      const pt = { lat: p.coords.latitude, lon: p.coords.longitude };
      setWhere(pt);
      setMe(pt);
    } catch {
      /* остаётся город из настроек намаза */
    }
  }, []);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- определить место при открытии
    locate();
  }, [locate]);

  const fetchArea = useCallback(async (b: string) => {
    bbox.current = b;
    const key = `places:${b}:${cat}:${query}:${verified}`;
    try {
      const r = await api<{ items: P[]; categories: Cat[] }>(`/places/map/?bbox=${b}&category=${cat}&q=${encodeURIComponent(query)}${verified ? '&verified=1' : ''}`);
      setItems(r.items);
      if (r.categories?.length) setCats(r.categories);
      save(key, r.items);
    } catch {
      setItems(await load<P[]>(key, []));
    }
  }, [cat, query, verified]);
  // первая область — вокруг найденного места; дальше — по движению карты
  useEffect(() => {
    if (!where) return;
    const d = 0.08;
    fetchArea(bbox.current || [where.lat - d, where.lon - d * 1.5, where.lat + d, where.lon + d * 1.5].map((x) => x.toFixed(4)).join(','));
  }, [where, fetchArea]);

  const from = me ?? where;
  const sorted = [...items].map((p) => ({ ...p, km: from ? distanceKm(from, p) : 0 })).sort((a, b) => a.km - b.km);
  const dist = (km: number) => (km < 1 ? t('{m} м', { m: Math.round(km * 1000) }) : t('{n} км', { n: km < 10 ? km.toFixed(1) : Math.round(km) }));
  const route = (p: P) => Linking.openURL(Platform.OS === 'ios' ? `maps://?daddr=${p.lat},${p.lon}` : `geo:0,0?q=${p.lat},${p.lon}(${encodeURIComponent(p.name)})`)
    .catch(() => Linking.openURL(`https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lon}`));
  const markers = items.map((p) => ({ id: p.id, lat: p.lat, lon: p.lon, title: p.name, sub: p.category_name, mosque: p.category === 'mosque',
    icon: p.icon, kind: p.category, selected: sel?.id === p.id }));
  const floating = { backgroundColor: c.card, shadowColor: '#000', shadowOpacity: 0.18, shadowRadius: 12, shadowOffset: { width: 0, height: 4 }, elevation: 5 };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top']}>
      <OfflineBar />
      <View style={{ flex: 1 }}>
        {where ? (
          <PlacesMap rounded={false} center={where} me={me} markers={markers}
            onSelect={(id) => setSel(items.find((x) => x.id === id) ?? null)}
            onMove={(b) => fetchArea(b.map((x) => x.toFixed(4)).join(','))} />
        ) : null}
        {/* поиск и категории поверх карты */}
        <View style={{ position: 'absolute', left: 10, right: 10, top: 8, gap: 8 }} pointerEvents="box-none">
          <View style={[floating, { flexDirection: 'row', alignItems: 'center', gap: 8, height: 48, borderRadius: 24, paddingLeft: inTab ? 16 : 6, paddingRight: 6 }]}>
            {!inTab ? <Pressable onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} hitSlop={8} style={{ padding: 4 }}><Icon name="chevron-back" size={24} color={c.accent} /></Pressable> : <Icon name="search" size={19} color={c.inkSoft} />}
            <TextInput value={q} onChangeText={setQ} onSubmitEditing={() => setQuery(q.trim())} returnKeyType="search" placeholder={t('Мечеть, кафе, адрес…')} placeholderTextColor={c.inkSoft}
              style={{ flex: 1, fontSize: 16, color: c.ink, paddingVertical: 0 }} />
            {q ? <Pressable onPress={() => { setQ(''); setQuery(''); }} hitSlop={8} style={{ padding: 6 }}><Icon name="close-circle" size={19} color={c.inkSoft} /></Pressable> : null}
            <Pressable onPress={() => (user ? router.push('/publish/places') : router.push('/login'))} hitSlop={6}
              style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: c.accent, alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="add" size={22} color="#fff" />
            </Pressable>
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingRight: 10 }}>
            {[{ key: '', name: t('Все'), icon: '' }, ...cats].map((x) => (
              <Pressable key={x.key || 'all'} onPress={() => setCat(x.key)}
                style={[floating, { flexDirection: 'row', alignItems: 'center', gap: 6, height: 36, paddingHorizontal: 13, borderRadius: 18, backgroundColor: cat === x.key ? c.accent : c.card }]}>
                {x.icon ? <PlaceIcon icon={x.icon} size={16} color={cat === x.key ? '#fff' : undefined} /> : null}
                <Txt style={{ fontWeight: '700', fontSize: 14 }} color={cat === x.key ? '#fff' : c.ink}>{x.name}</Txt>
              </Pressable>
            ))}
            <Pressable onPress={() => setVerified(!verified)}
              style={[floating, { flexDirection: 'row', alignItems: 'center', gap: 5, height: 36, paddingHorizontal: 13, borderRadius: 18, backgroundColor: verified ? c.ok : c.card }]}>
              <Icon name="checkmark-circle" size={15} color={verified ? '#fff' : c.ok} />
              <Txt style={{ fontWeight: '700', fontSize: 14 }} color={verified ? '#fff' : c.ink}>{t('Проверенные')}</Txt>
            </Pressable>
          </ScrollView>
        </View>
        {/* «где я» */}
        <Pressable onPress={locate} accessibilityLabel={t('Где я')}
          style={[floating, { position: 'absolute', right: 12, bottom: (sel ? 170 : 92) + (listOpen ? 300 : 0), width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' }]}>
          <Icon name="navigate" size={22} color="#1e88e5" />
        </Pressable>
        {/* выбранное место */}
        {sel ? (
          <Animated.View entering={FadeInDown.duration(180)} exiting={FadeOut.duration(120)}
            style={[floating, { position: 'absolute', left: 10, right: 10, bottom: 82 + (listOpen ? 300 : 0), borderRadius: 20, padding: 12, gap: 8 }]}>
            <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
              {sel.photo ? <Image source={{ uri: sel.photo }} style={{ width: 52, height: 52, borderRadius: 14 }} contentFit="cover" />
                : <View style={{ width: 52, height: 52, borderRadius: 14, backgroundColor: c.card2, alignItems: 'center', justifyContent: 'center' }}><PlaceIcon icon={sel.icon} size={25} /></View>}
              <View style={{ flex: 1 }}>
                <Txt style={{ fontWeight: '800', fontSize: 16 }} numberOfLines={1}>{sel.name}</Txt>
                <Txt kind="small" numberOfLines={1}>{sel.category_name}{sel.address ? ` · ${sel.address}` : ''}</Txt>
                {sel.brief ? <Txt kind="small" color={c.ok} numberOfLines={1} style={{ fontWeight: '600' }}>{sel.brief}</Txt> : null}
              </View>
              <Pressable onPress={() => setSel(null)} hitSlop={10}><Icon name="close" size={20} color={c.inkSoft} /></Pressable>
            </View>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Pressable onPress={() => route(sel)} style={{ flex: 1, flexDirection: 'row', gap: 6, alignItems: 'center', justifyContent: 'center', height: 42, borderRadius: 21, backgroundColor: c.accent }}>
                <Icon name="navigate" size={17} color="#fff" /><Txt color="#fff" style={{ fontWeight: '800' }}>{t('Маршрут')}{from ? ` · ${dist(distanceKm(from, sel))}` : ''}</Txt>
              </Pressable>
              {sel.phone ? <Pressable onPress={() => Linking.openURL(`tel:${sel.phone!.replace(/[^+\d]/g, '')}`)} style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
                <Icon name="call" size={18} color={c.accentD} /></Pressable> : null}
              <Pressable onPress={() => router.push(`/pub/places/${sel.id}`)} style={{ height: 42, paddingHorizontal: 16, borderRadius: 21, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
                <Txt color={c.accentD} style={{ fontWeight: '800' }}>{t('Подробнее')}</Txt>
              </Pressable>
            </View>
          </Animated.View>
        ) : null}
        {/* список рядом: свёрнут — полоска, развернуть — нажатием */}
        <View style={[floating, { position: 'absolute', left: 0, right: 0, bottom: 0, borderTopLeftRadius: 22, borderTopRightRadius: 22, height: listOpen ? 370 : 72 }]}>
          <Pressable onPress={() => setListOpen(!listOpen)} style={{ alignItems: 'center', paddingTop: 7, paddingBottom: 6 }}>
            <View style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: c.line }} />
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 }}>
              <Txt style={{ fontWeight: '800', fontSize: 16 }}>{items.length ? t('Мест рядом: {n}', { n: items.length }) : t('Здесь пока ничего нет')}</Txt>
              <Icon name={listOpen ? 'chevron-down' : 'chevron-up'} size={17} color={c.inkSoft} />
            </View>
          </Pressable>
          {listOpen ? (
            <FlatList data={sorted} keyExtractor={(p) => String(p.id)} contentContainerStyle={{ paddingHorizontal: 10, paddingBottom: 16 }}
              renderItem={({ item: p }) => (
                <Pressable onPress={() => { setSel(p); setListOpen(false); }} style={({ pressed }) => ({ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 8, borderRadius: 14, backgroundColor: pressed ? c.card2 : 'transparent' })}>
                  <View style={{ width: 44, height: 44, borderRadius: 14, backgroundColor: c.card2, alignItems: 'center', justifyContent: 'center' }}><PlaceIcon icon={p.icon} size={22} /></View>
                  <View style={{ flex: 1 }}>
                    <Txt style={{ fontWeight: '700' }} numberOfLines={1}>{p.name}{p.verif === 'ilm4' ? ' ✓' : ''}</Txt>
                    <Txt kind="small" numberOfLines={1}>{p.category_name}{p.address ? ` · ${p.address}` : ''}</Txt>
                  </View>
                  <Txt kind="small" style={{ fontWeight: '700' }}>{dist(p.km)}</Txt>
                </Pressable>
              )}
              ListEmptyComponent={<Txt kind="muted" style={{ textAlign: 'center', padding: 16 }}>{t('Отдалите карту или выберите другую категорию. Знаете место? Добавьте его — кнопка «+».')}</Txt>} />
          ) : null}
        </View>
      </View>
    </SafeAreaView>
  );
}
