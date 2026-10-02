import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView, Switch, View } from 'react-native';

import { load, save } from '@/lib/storage';
import { useApp } from '@/state/app';
import { Button, Card, Chip, Field, Loading, Screen, Section, Txt } from '@/ui/kit';
import { RangeSlider } from '@/ui/range';
import { useFetch } from '@/ui/useFetch';

type F = Record<string, any>;

export default function NikahFilters() {
  const { c, t, user } = useApp();
  const other = user?.nikah?.gender === 'M' ? 'F' : 'M';
  const { data: o } = useFetch<any>(`/nikah/options/?gender=${other}`);
  const [f, setF] = useState<F | null>(null);
  useEffect(() => { load<F>('nikah_filters', {}).then(setF); }, []);
  if (!o || !f) return <Screen back title={t('Фильтры')}><Loading /></Screen>;

  const set = (k: string, v: any) => setF((old) => {
    const n = { ...old };
    if (v === '' || v === false || v === undefined) delete n[k];
    else n[k] = v;
    return n;
  });
  const range = (k: string, def: [number, number]) => (f[k] as [number, number]) ?? def;
  const setRange = (k: string, def: [number, number], v: [number, number]) => set(k, v[0] === def[0] && v[1] === def[1] ? '' : v);
  const chips = (k: string, list: { key: string; name: string }[]) => (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
      <Chip label={t('Любой')} on={!f[k]} onPress={() => set(k, '')} />
      {list.map((x) => <Chip key={x.key} label={x.name} on={f[k] === x.key} onPress={() => set(k, x.key)} />)}
    </ScrollView>
  );
  const R = o.ranges;
  const apply = async () => {
    await save('nikah_filters', f);
    router.back();
  };
  const toggle = (k: string, label: string) => (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 6 }}>
      <Txt style={{ flex: 1 }}>{label}</Txt>
      <Switch value={!!f[k]} onValueChange={(v) => set(k, v)} trackColor={{ true: c.accent, false: c.line }} />
    </View>
  );

  return (
    <Screen back title={t('Фильтры')} right={<Chip label={t('Сбросить')} onPress={() => setF({})} />}>
      <Card style={{ gap: 18 }}>
        <RangeSlider label={t('Возраст')} min={R.age[0]} max={R.age[1]} value={range('age', R.age)} onChange={(v) => setRange('age', R.age, v)} />
        <RangeSlider label={t('Рост')} unit={` ${t('см')}`} min={R.height[0]} max={R.height[1]} value={range('height', R.height)} onChange={(v) => setRange('height', R.height, v)} />
        <RangeSlider label={t('Вес')} unit={` ${t('кг')}`} min={R.weight[0]} max={R.weight[1]} value={range('weight', R.weight)} onChange={(v) => setRange('weight', R.weight, v)} />
      </Card>
      <Section title={t('Где')}>
        <Field placeholder={t('Страна')} value={f.country ?? ''} onChangeText={(v) => set('country', v)} />
        <Field placeholder={t('Город')} value={f.city ?? ''} onChangeText={(v) => set('city', v)} />
      </Section>
      <Section title={t('Национальность')}>
        {chips('nation_group', o.nation_groups)}
        <Field placeholder={t('Или впишите: узбечка, чеченка…')} value={f.nation_text ?? ''} onChangeText={(v) => set('nation_text', v)} />
      </Section>
      <Section title={t('Мазхаб')}>{chips('madhhab', o.madhhab)}</Section>
      <Section title={t('Вероубеждение')}>{chips('aqida', o.aqida)}</Section>
      <Section title={t('Намаз')}>{chips('prayer', o.prayer)}</Section>
      <Section title={other === 'M' ? t('Борода') : t('Покрытие')}>{chips('look', o.look)}</Section>
      <Section title={t('Готовность к никяху')}>{chips('ready_when', o.ready_when)}</Section>
      <Section title={t('Переезд')}>{chips('relocation', o.relocation)}</Section>
      <Card style={{ paddingVertical: 6 }}>
        {toggle('with_photo', t('Только с фото (при симпатии)'))}
        {toggle('never_married', other === 'M' ? t('Не был женат') : t('Не была замужем'))}
        {toggle('no_children', t('Без детей'))}
        {toggle('online', t('Сейчас в сети (премиум)'))}
        {other === 'F' ? toggle('polygyny', t('Готова быть не первой женой')) : null}
      </Card>
      <Button title={t('Показать')} onPress={apply} />
    </Screen>
  );
}
