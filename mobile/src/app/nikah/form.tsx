import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Chip, Field, Icon, Loading, Txt } from '@/ui/kit';
import { OptionList } from '@/ui/options';
import { RangeSlider } from '@/ui/range';

type D = Record<string, any>;

// шаг → поля (для перехода к ошибке с сервера)
const STEP_OF: Record<string, number> = {
  gender: 1, name: 2, age: 2, age_from: 2, age_to: 2, country: 3, city: 3, nationality: 3, height: 4, weight: 4,
  marital: 5, wife_number: 5, polygyny: 5, madhhab: 6, aqida: 6, prayer: 6, quran: 6, where_allah: 6,
  has_children: 7, children_want: 7, children_accept: 7, ready_when: 7, look: 8, manhaj_text: 9, relocation: 10,
  about: 11, partner_expectations: 12, photo_mode: 13, photo: 13, faith: 14, pledges: 15,
};

/** Анкета никяха: 15 шагов, как в боте. Правка — те же шаги без пола, вопросов и обязательств. */
export default function NikahForm() {
  const { c, t, user, refreshMe } = useApp();
  const editing = !!user?.nikah;
  const [d, setD] = useState<D>({ age: 25, age_from: 20, age_to: 35, height: 170, weight: 65, photo_mode: 'exchange' });
  const [o, setO] = useState<any>(null);
  const [step, setStep] = useState(editing ? 2 : 1);
  const [photo, setPhoto] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [countryQ, setCountryQ] = useState('');

  useEffect(() => {
    if (editing) api('/nikah/profile/raw/').then((r) => setD((old) => ({ ...old, ...r })));
  }, [editing]);
  useEffect(() => {
    if (d.gender) api(`/nikah/options/?gender=${d.gender}`).then(setO).catch((e) => Alert.alert(e.message));
  }, [d.gender]);

  const set = (k: string, v: any) => {
    setD((old) => ({ ...old, [k]: v }));
    setErrors((e) => ({ ...e, [k]: '' }));
  };
  const last = editing ? 13 : 15;
  const brother = d.gender === 'M';
  const cities: string[] = useMemo(() => (o?.cities?.[d.country] ?? []), [o, d.country]);

  const ok = (): string => {
    const need = (keys: string[]) => keys.every((k) => d[k] !== undefined && d[k] !== '' && d[k] !== null);
    switch (step) {
      case 1: return d.gender ? '' : t('Выберите вариант');
      case 2: return (d.name || '').trim() ? '' : t('Напишите имя или ник');
      case 3: return d.country ? '' : t('Выберите страну');
      case 5: return need(['marital']) && (brother ? true : need(['polygyny'])) ? '' : t('Выберите вариант');
      case 6: return need(['madhhab', 'aqida', 'prayer', 'quran', 'where_allah']) ? '' : t('Ответьте на все вопросы.');
      case 7: return need(['has_children', 'children_want', 'children_accept', 'ready_when']) ? '' : t('Ответьте на все вопросы.');
      case 8: return d.look ? '' : t('Выберите вариант');
      case 9: return (d.manhaj_text || '').trim().length >= 10 ? '' : t('Напишите хотя бы {minimum} символов', { minimum: 10 });
      case 10: return d.relocation ? '' : t('Выберите вариант');
      case 11: return (d.about || '').trim().length >= 20 ? '' : t('Напишите хотя бы {minimum} символов', { minimum: 20 });
      case 12: return (d.partner_expectations || '').trim().length >= 20 ? '' : t('Напишите хотя бы {minimum} символов', { minimum: 20 });
      case 13: return d.photo_mode === 'exchange' && !photo && !d.has_photo ? t('Загрузите фото или выберите «Без фото».') : '';
      case 14: return (o?.faith ?? []).every((q: any) => ['yes', 'no'].includes(d[`faith_${q.key}`])) ? '' : t('Ответьте на все вопросы.');
      case 15: return (o?.pledges ?? []).every((p: any) => d[`agree_${p.key}`]) ? '' : t('Примите все пункты, чтобы завершить регистрацию.');
      default: return '';
    }
  };

  const next = () => {
    const err = ok();
    if (err) return setErrors({ step: err });
    setErrors({});
    if (step < last) setStep(step + 1);
    else submit();
  };

  const submit = async () => {
    setBusy(true);
    try {
      const form = new FormData();
      for (const [k, v] of Object.entries(d)) {
        if (v === null || v === undefined || k === 'has_photo') continue;
        form.append(k, typeof v === 'boolean' ? (v ? '1' : '') : String(v));
      }
      if (photo) form.append('photo', { uri: photo.uri, name: photo.fileName || 'photo.jpg', type: photo.mimeType || 'image/jpeg' } as any);
      const r = await api('/nikah/profile/', { form, timeout: 60000 });
      await refreshMe();
      Alert.alert(r.message);
      router.back();
    } catch (e) {
      const err = e as ApiError;
      setErrors({ ...err.fields, step: err.message });
      const steps = Object.keys(err.fields || {}).map((k) => STEP_OF[k] ?? 1);
      if (steps.length) setStep(Math.min(...steps));
    } finally {
      setBusy(false);
    }
  };

  const pick = async () => {
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, aspect: [3, 4], quality: 0.85 });
    if (!r.canceled && r.assets[0]) setPhoto(r.assets[0]);
  };

  const title: Record<number, string> = {
    1: t('Кто вы?'), 2: t('Имя и возраст'), 3: t('Откуда вы'), 4: t('Рост и вес'), 5: t('Семейное положение'), 6: t('Религия'),
    7: t('Дети и сроки'), 8: brother ? t('Борода') : t('Покрытие'), 9: t('Вероубеждение и манхадж своими словами'), 10: t('Переезд'),
    11: t('О себе'), 12: brother ? t('Какую жену ищете') : t('Какого мужа ищете'), 13: t('Фото'), 14: t('Закрытые вопросы'), 15: t('Обязательства'),
  };
  const q = (label: string, key: string, list?: any[]) => (
    <View style={{ gap: 8 }}>
      <Txt kind="h3">{label}</Txt>
      {list ? <OptionList options={list} value={d[key]} onChange={(v) => set(key, v)} /> : null}
      {errors[key] ? <Txt kind="small" color={c.bad}>{errors[key]}</Txt> : null}
    </View>
  );

  if (editing && !d.gender) return <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }}><Loading /></SafeAreaView>;
  const needOpts = step >= 2 && !o;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top', 'bottom']}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 16, paddingBottom: 8 }}>
        <Pressable onPress={() => (step > (editing ? 2 : 1) ? setStep(step - 1) : router.back())} hitSlop={12}>
          <Icon name="chevron-back" size={26} color={c.accent} />
        </Pressable>
        <View style={{ flex: 1, height: 6, borderRadius: 3, backgroundColor: c.line }}>
          <View style={{ width: `${(step / last) * 100}%`, height: 6, borderRadius: 3, backgroundColor: c.accent }} />
        </View>
        <Txt kind="small">{step}/{last}</Txt>
      </View>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={{ padding: 16, gap: 16, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
          <Txt kind="h1">{title[step]}</Txt>
          {needOpts ? <Loading /> : null}
          {step === 1 ? (
            <OptionList options={[{ key: 'M', name: t('Я брат — ищу жену') }, { key: 'F', name: t('Я сестра — ищу мужа') }]}
              value={d.gender} onChange={(v) => set('gender', v)} />
          ) : null}
          {step === 2 && o ? (
            <>
              <Field label={t('Имя или ник')} value={d.name ?? ''} onChangeText={(v) => set('name', v)} maxLength={40} error={errors.name} />
              <RangeSlider single label={t('Ваш возраст')} min={18} max={80} value={[d.age, d.age]} onChange={([v]) => set('age', v)} />
              <RangeSlider label={brother ? t('Возраст жены') : t('Возраст мужа')} min={18} max={80} value={[d.age_from, d.age_to]}
                onChange={([a, b]) => setD((x) => ({ ...x, age_from: a, age_to: b }))} />
            </>
          ) : null}
          {step === 3 && o ? (
            <>
              {d.country ? <Chip label={`✓ ${d.country}`} on onPress={() => set('country', '')} /> : (
                <>
                  <Field placeholder={t('Поиск страны')} value={countryQ} onChangeText={setCountryQ} />
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                    {(o.countries as string[]).filter((x) => !countryQ || x.toLowerCase().startsWith(countryQ.toLowerCase())).slice(0, countryQ ? 40 : 24)
                      .map((x) => <Chip key={x} label={x} onPress={() => { set('country', x); set('city', ''); }} />)}
                  </View>
                </>
              )}
              {d.country ? (
                <>
                  <Field label={t('Город')} value={d.city ?? ''} onChangeText={(v) => set('city', v)} />
                  {cities.length ? (
                    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                      {cities.map((x) => <Chip key={x} label={x} on={d.city === x} onPress={() => set('city', x)} />)}
                    </View>
                  ) : null}
                </>
              ) : null}
              <Field label={t('Национальность')} value={d.nationality ?? ''} onChangeText={(v) => set('nationality', v)} maxLength={80} />
            </>
          ) : null}
          {step === 4 ? (
            <>
              <RangeSlider single label={t('Рост')} unit={` ${t('см')}`} min={120} max={230} value={[d.height ?? 170, d.height ?? 170]} onChange={([v]) => set('height', v)} />
              <RangeSlider single label={t('Вес')} unit={` ${t('кг')}`} min={40} max={200} value={[d.weight ?? 65, d.weight ?? 65]} onChange={([v]) => set('weight', v)} />
            </>
          ) : null}
          {step === 5 && o ? (
            <>
              {q('', 'marital', o.marital)}
              {brother && d.marital === 'married' ? q(t('Какую по счёту жену ищете?'), 'wife_number', o.wife_number.filter((x: any) => x.key > 1)) : null}
              {!brother ? q(t('Готовы ли быть не первой женой?'), 'polygyny', o.polygyny) : null}
            </>
          ) : null}
          {step === 6 && o ? (
            <>
              {q(t('Мазхаб'), 'madhhab', o.madhhab)}
              {q(t('Вероубеждение'), 'aqida', o.aqida)}
              {q(t('Намаз'), 'prayer', o.prayer)}
              {q(t('Чтение Корана'), 'quran', o.quran)}
              {q(t('Где Аллах?'), 'where_allah', o.where_allah)}
            </>
          ) : null}
          {step === 7 && o ? (
            <>
              {q(t('Есть свои дети?'), 'has_children', o.has_children)}
              {q(t('Хотите детей?'), 'children_want', o.children_want)}
              {q(t('Примете детей партнёра?'), 'children_accept', o.children_accept)}
              {q(t('Когда готовы к никяху?'), 'ready_when', o.ready_when)}
            </>
          ) : null}
          {step === 8 && o ? q('', 'look', o.look) : null}
          {step === 9 ? (
            <Field multiline value={d.manhaj_text ?? ''} onChangeText={(v) => set('manhaj_text', v)} maxLength={900}
              placeholder={t('Кого из учёных слушаете, как понимаете Коран и Сунну…')} error={errors.manhaj_text} />
          ) : null}
          {step === 10 && o ? q('', 'relocation', o.relocation) : null}
          {step === 11 ? (
            <Field multiline value={d.about ?? ''} onChangeText={(v) => set('about', v)} maxLength={900}
              placeholder={t('Характер, работа, увлечения, как проводите время…')} error={errors.about} />
          ) : null}
          {step === 12 ? (
            <Field multiline value={d.partner_expectations ?? ''} onChangeText={(v) => set('partner_expectations', v)} maxLength={900}
              placeholder={t('Какие качества важны, что ожидаете от семьи…')} error={errors.partner_expectations} />
          ) : null}
          {(step === 9 || step === 11 || step === 12) ? <Txt kind="small">{t('Без телефонов, ников и ссылок — такие анкеты отклоняются.')}</Txt> : null}
          {step === 13 && o ? (
            <>
              <OptionList options={o.photo_mode} value={d.photo_mode} onChange={(v) => set('photo_mode', v)} />
              {d.photo_mode === 'exchange' ? (
                <Pressable onPress={pick} style={{ alignItems: 'center', gap: 8, padding: 16, borderRadius: 20, borderWidth: 1.5, borderStyle: 'dashed', borderColor: c.accent }}>
                  {photo ? <Image source={{ uri: photo.uri }} style={{ width: 150, height: 200, borderRadius: 16 }} contentFit="cover" />
                    : <Icon name="image-outline" size={40} color={c.accent} />}
                  <Txt color={c.accent} style={{ fontWeight: '700' }}>{photo ? t('Выбрать другое') : d.has_photo ? t('Фото загружено · заменить') : t('Выбрать фото')}</Txt>
                </Pressable>
              ) : null}
              <Txt kind="small">{t('Фото хранится зашифрованным. Его увидит только тот, с кем взаимная симпатия, один раз и с водяным знаком.')}</Txt>
            </>
          ) : null}
          {step === 14 && o ? (
            <>
              <Txt kind="muted">{t('Ответы видит только модератор — другим они не показываются.')}</Txt>
              {o.faith.map((x: any) => (
                <View key={x.key} style={{ gap: 8 }}>
                  <Txt kind="h3">{x.question}</Txt>
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    <Chip label={x.yes} on={d[`faith_${x.key}`] === 'yes'} onPress={() => set(`faith_${x.key}`, 'yes')} />
                    <Chip label={x.no} on={d[`faith_${x.key}`] === 'no'} onPress={() => set(`faith_${x.key}`, 'no')} />
                  </View>
                </View>
              ))}
            </>
          ) : null}
          {step === 15 && o ? o.pledges.map((p: any) => (
            <Pressable key={p.key} onPress={() => set(`agree_${p.key}`, !d[`agree_${p.key}`])} style={{ flexDirection: 'row', gap: 12, padding: 14, borderRadius: 16,
              backgroundColor: d[`agree_${p.key}`] ? c.accentSoft : c.card, borderWidth: 1.5, borderColor: d[`agree_${p.key}`] ? c.accent : c.line }}>
              <Icon name={d[`agree_${p.key}`] ? 'checkbox' : 'square-outline'} color={c.accent} />
              <View style={{ flex: 1 }}><Txt kind="h3">{p.title}</Txt><Txt kind="small">{p.text}</Txt></View>
            </Pressable>
          )) : null}
          {errors.step ? <Txt color={c.bad}>{errors.step}</Txt> : null}
        </ScrollView>
        <View style={{ padding: 16, paddingTop: 8 }}>
          <Button title={step === last ? (editing ? t('Сохранить') : t('Отправить на проверку')) : t('Далее')} onPress={next} loading={busy} />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
