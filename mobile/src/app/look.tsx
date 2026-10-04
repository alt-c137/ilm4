import { router } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp, type Design, type TabKey, type User } from '@/state/app';
import { Button, Icon, Screen, toast, Txt } from '@/ui/kit';

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : 'Нет соединения');
type Row = { key: string; name: string; about: string; on: boolean };
type Data = { design: Design; desk: string; custom: boolean; designs: (Row & { desk: string })[]; desks: (Row & { tabs: string[]; tabs_app: string[] })[]; me: User };

/** Маленький «телефон» с нижней панелью такого вида — чтобы выбирать глазами, а не по названию. */
function Phone({ design }: { design: string }) {
  const { c } = useApp();
  const dot = (i: number) => {
    const first = i === 0;
    if (design === 'telegram' && first) return <View key={i} style={{ width: 16, height: 9, borderRadius: 5, backgroundColor: c.accentSoft, borderWidth: 1, borderColor: c.accent }} />;
    if (design === 'classic' && i === 2) return <View key={i} style={{ width: 13, height: 9, borderRadius: 3, backgroundColor: c.accent, marginTop: -5 }} />;
    if (design === 'insta') return <View key={i} style={{ width: 7, height: 7, borderRadius: i === 4 ? 4 : 2, borderWidth: first ? 0 : 1.2, borderColor: c.inkSoft, backgroundColor: first ? c.ink : 'transparent' }} />;
    const color = first ? (design === 'avito' || design === 'x' ? c.ink : c.accent) : design === 'avito' && i === 2 ? c.accent : c.inkSoft;
    return <View key={i} style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: color, opacity: first || (design === 'avito' && i === 2) ? 1 : 0.6 }} />;
  };
  const pill = design === 'telegram';
  return (
    <View style={{ width: 74, height: 118, borderRadius: 14, backgroundColor: c.bg, borderWidth: 1.5, borderColor: c.line, overflow: 'hidden', alignSelf: 'center' }}>
      <View style={{ margin: 6, marginBottom: 6, height: 9, borderRadius: 5, backgroundColor: c.card }} />
      {[0, 1, 2].map((i) => <View key={i} style={{ marginHorizontal: 6, marginBottom: 5, height: 15, borderRadius: 5, backgroundColor: c.card }} />)}
      {design === 'x' ? <View style={{ position: 'absolute', right: 6, bottom: 23, width: 15, height: 15, borderRadius: 8, backgroundColor: c.accent }} /> : null}
      <View style={{ position: 'absolute', left: pill ? 5 : 0, right: pill ? 5 : 0, bottom: pill ? 5 : 0, height: pill ? 16 : 17, borderRadius: pill ? 8 : 0, backgroundColor: c.card,
        borderTopWidth: pill ? 0 : 1, borderWidth: pill ? 1 : 0, borderColor: c.line, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', paddingHorizontal: 4 }}>
        {[0, 1, 2, 3, 4].map(dot)}
      </View>
    </View>
  );
}

/** «Вид и рабочий стол»: знакомый дизайн оболочки + готовый набор кнопок под задачу. first=1 — экран первого входа. */
export default function Look() {
  const { c, t, setUser, setTabs } = useApp();
  const [data, setData] = useState<Data | null>(null);
  const [design, setDesign] = useState<Design>('classic');
  const [desk, setDesk] = useState('');
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Data>('/me/look/').then((d) => { setData(d); setDesign(d.design); setDesk(d.custom ? '' : d.desk); }).catch((e) => toast(errorText(e)));
  }, []);
  const pickDesign = useCallback((d: Data['designs'][number]) => {
    setDesign(d.key as Design);
    if (!touched) setDesk(d.desk);                // выбрал дизайн — подставляем подходящий ему стол (если стол не трогали)
  }, [touched]);
  const apply = async () => {
    if (!data) return;
    setBusy(true);
    try {
      const r = await api<Data>('/me/look/', { body: { design, desk } });
      setUser(r.me);
      const chosen = r.desks.find((x) => x.key === desk);
      if (chosen) setTabs(chosen.tabs_app as TabKey[]);
      toast(t('Сохранено'));
      router.back();
    } catch (e) { toast(errorText(e)); } finally { setBusy(false); }
  };
  if (!data) return <Screen title={t('Вид и рабочий стол')} back><ActivityIndicator color={c.accent} style={{ marginTop: 40 }} /></Screen>;
  return (
    <Screen title={t('Вид и рабочий стол')} back>
      <View style={{ gap: 4 }}>
        <Txt kind="h3">{t('Дизайн')}</Txt>
        <Txt kind="small">{t('Привычный вид оболочки. Содержимое ilm4 то же самое — меняется только рамка вокруг.')}</Txt>
      </View>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        {data.designs.map((d) => (
          <Pressable key={d.key} onPress={() => pickDesign(d)} accessibilityRole="radio" accessibilityState={{ selected: design === d.key }}
            style={{ width: '47.8%', padding: 12, gap: 3, borderRadius: 18, backgroundColor: c.card, borderWidth: 2, borderColor: design === d.key ? c.accent : 'transparent' }}>
            <Phone design={d.key} />
            <Txt style={{ fontWeight: '700', fontSize: 14.5, marginTop: 6 }}>{d.name}</Txt>
            <Txt kind="small" style={{ fontSize: 12 }}>{d.about}</Txt>
          </Pressable>
        ))}
      </View>
      <View style={{ gap: 4 }}>
        <Txt kind="h3">{t('Рабочий стол')}</Txt>
        <Txt kind="small">{t('Готовый набор под задачу: какие кнопки внизу и с чего открывается ilm4. Любой набор потом можно подправить под себя.')}</Txt>
      </View>
      <View style={{ backgroundColor: c.card, borderRadius: 18, overflow: 'hidden' }}>
        {data.desks.map((d, i) => (
          <Pressable key={d.key} onPress={() => { setDesk(d.key); setTouched(true); }} accessibilityRole="radio" accessibilityState={{ selected: desk === d.key }}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11, paddingHorizontal: 16, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
            <View style={{ flex: 1, gap: 1 }}>
              <Txt style={{ fontSize: 15.5, fontWeight: '500' }}>{d.name}</Txt>
              <Txt kind="small">{d.about}</Txt>
              <Txt kind="small" color={c.accent}>{d.tabs.join(' · ')}</Txt>
            </View>
            <View style={{ width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: desk === d.key ? c.accent : c.inkSoft, alignItems: 'center', justifyContent: 'center' }}>
              {desk === d.key ? <View style={{ width: 12, height: 12, borderRadius: 6, backgroundColor: c.accent }} /> : null}
            </View>
          </Pressable>
        ))}
        <Pressable onPress={() => router.push('/tabs-setup')} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, paddingHorizontal: 16, borderTopWidth: 0.5, borderTopColor: c.line }}>
          <View style={{ flex: 1, gap: 1 }}>
            <Txt color={c.accent} style={{ fontSize: 15.5, fontWeight: '500' }}>{t('Собрать свой набор')}</Txt>
            <Txt kind="small">{t('Выбрать кнопки по одной, порядок и стартовый экран')}</Txt>
          </View>
          <Icon name="chevron-forward" size={18} color={c.inkSoft} />
        </Pressable>
      </View>
      <Button title={t('Применить')} onPress={apply} loading={busy} />
    </Screen>
  );
}
