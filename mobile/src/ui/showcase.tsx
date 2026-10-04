/**
 * «Витрина» — вид главной, где каждый сервис показан живой плиткой своего цвета: свежие объявления, вакансии,
 * поездки, «новых сообщений: 3»… Данные — с сервера (apps/core/showcase.py), одни и те же для сайта и приложения.
 * Плитки можно переставить и убрать лишние: долгое нажатие на плитку.
 */
import { Image } from 'expo-image';
import { useState } from 'react';
import { Alert, Pressable, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { openSiteUrl, openWeb } from '@/lib/links';
import { MODULE_ICON, openModule } from '@/lib/modules';
import { useApp } from '@/state/app';

import { Icon, Loading, Sheet, Txt } from './kit';
import { useFetch } from './useFetch';

type Row = { title: string; sub: string; image: string; web: string };
type Widget = { key: string; title: string; color: string; icon: string; descr: string; items: Row[]; note: string; count: number | null; hot: boolean;
  web: string; action: { label: string; url: string; web: string } | null };
type Data = { items: Widget[]; hidden: { key: string; title: string }[] };

export function Showcase({ skip = [] }: { skip?: string[] }) {
  const { c, t, user, dark } = useApp();
  const { data, setData, loading } = useFetch<Data>('/home/showcase/');
  const [menu, setMenu] = useState<Widget | null>(null);
  if (!data) return loading ? <Loading /> : null;

  const arrange = async (key: string, action: string) => {
    try {
      setData(await api<Data>('/home/showcase/', { body: { key, action } }));
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const open = (w: Widget) => openModule(w.key, 'on', w.title);
  const soft = (hex: string, a: string) => `${hex}${a}`;
  const items = data.items.filter((w) => !skip.includes(w.key));

  return (
    <View style={{ gap: 12 }}>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12 }}>
        {items.map((w) => {
          const big = w.items.length > 0;
          return (
            <Pressable key={w.key} onPress={() => open(w)} onLongPress={user ? () => setMenu(w) : undefined} delayLongPress={350}
              style={({ pressed }) => ({ width: big ? '100%' : '47.8%', flexGrow: big ? 0 : 1, backgroundColor: c.card, borderRadius: 22, overflow: 'hidden', opacity: pressed ? 0.85 : 1 })}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 11, padding: 12, backgroundColor: soft(w.color, dark ? '33' : '1c') }}>
                <View style={{ width: 40, height: 40, borderRadius: 13, backgroundColor: w.color, alignItems: 'center', justifyContent: 'center' }}>
                  {w.icon && w.icon.endsWith('.png') ? <Image source={{ uri: w.icon }} style={{ width: 22, height: 22, tintColor: '#fff' }} />
                    : <Icon name={MODULE_ICON[w.key] ?? 'apps'} size={21} color="#fff" />}
                </View>
                <Txt style={{ flex: 1, fontWeight: '800', fontSize: 16 }} numberOfLines={1}>{w.title}</Txt>
                {w.count ? <View style={{ backgroundColor: soft(w.color, '26'), borderRadius: 999, paddingHorizontal: 9, paddingVertical: 2 }}><Txt style={{ fontSize: 12, fontWeight: '800' }} color={w.color}>{w.count}</Txt></View> : null}
              </View>
              <View style={{ padding: 12, gap: 8 }}>
                {w.note ? <Txt kind="small" color={w.hot ? w.color : undefined} style={{ fontSize: 14, fontWeight: w.hot ? '700' : '400' }} numberOfLines={2}>{w.note}</Txt>
                  : !big ? <Txt kind="small" style={{ fontSize: 13.5 }} numberOfLines={3}>{w.descr}</Txt> : null}
                {w.items.map((x, i) => (
                  <Pressable key={i} onPress={() => openSiteUrl(x.web)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    {x.image ? <Image source={{ uri: x.image }} style={{ width: 38, height: 38, borderRadius: 11 }} contentFit="cover" />
                      : <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: w.color, marginHorizontal: 6 }} />}
                    <View style={{ flex: 1 }}>
                      <Txt style={{ fontWeight: '600', fontSize: 14.5 }} numberOfLines={1}>{x.title}</Txt>
                      {x.sub ? <Txt kind="small" numberOfLines={1} style={{ fontSize: 12.5 }}>{x.sub}</Txt> : null}
                    </View>
                  </Pressable>
                ))}
                {big ? (
                  <View style={{ flexDirection: 'row', gap: 8, marginTop: 2 }}>
                    <View style={{ flex: 1, alignItems: 'center', paddingVertical: 9, borderRadius: 12, backgroundColor: w.color }}><Txt color="#fff" style={{ fontWeight: '800', fontSize: 14 }}>{t('Открыть')}</Txt></View>
                    {w.action ? (
                      <Pressable onPress={() => openWeb(w.action!.url)} style={{ flex: 1, alignItems: 'center', paddingVertical: 9, borderRadius: 12, backgroundColor: soft(w.color, '1f') }}>
                        <Txt color={w.color} style={{ fontWeight: '800', fontSize: 14 }} numberOfLines={1}>{w.action.label}</Txt>
                      </Pressable>
                    ) : null}
                  </View>
                ) : null}
              </View>
            </Pressable>
          );
        })}
      </View>
      {user ? <Txt kind="small" style={{ textAlign: 'center' }}>{t('Долгое нажатие на плитку — переставить или убрать.')}</Txt> : null}
      {data.hidden.length ? (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          <Txt kind="small">{t('Убраны с витрины:')}</Txt>
          {data.hidden.map((h) => (
            <Pressable key={h.key} onPress={() => arrange(h.key, 'show')} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, borderWidth: 1, borderColor: c.line, borderStyle: 'dashed', borderRadius: 999, paddingHorizontal: 11, paddingVertical: 5 }}>
              <Icon name="add" size={14} color={c.inkSoft} /><Txt kind="small">{h.title}</Txt>
            </Pressable>
          ))}
        </View>
      ) : null}
      <Sheet open={!!menu} onClose={() => setMenu(null)} title={menu?.title} items={menu ? [
        { icon: 'arrow-up-outline', title: t('Выше'), onPress: () => arrange(menu.key, 'up') },
        { icon: 'arrow-down-outline', title: t('Ниже'), onPress: () => arrange(menu.key, 'down') },
        { icon: 'eye-off-outline', title: t('Убрать с витрины'), onPress: () => arrange(menu.key, 'hide') },
      ] : []} />
    </View>
  );
}
