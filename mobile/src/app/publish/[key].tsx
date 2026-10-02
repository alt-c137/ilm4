import DateTimePicker from '@react-native-community/datetimepicker';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, Switch, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { openWeb } from '@/lib/links';
import { useApp } from '@/state/app';
import { Button, Card, Chip, Field, Icon, Loading, Row, Screen, Txt } from '@/ui/kit';
import { OptionList } from '@/ui/options';

type F = { name: string; label: string; kind: string; required: boolean; help: string; max_length: number | null;
  choices?: { key: string | number; name: string }[]; value?: any };
type Schema = { key: string; title: string; fields: F[]; editing: boolean; pledge: string[]; price: number; geo: boolean };

/** Подача и правка публикации. Поля приходят с сервера (те же формы и проверки, что на сайте). */
export default function Publish() {
  const { key, id } = useLocalSearchParams<{ key: string; id?: string }>();
  const { c, t } = useApp();
  const [s, setS] = useState<Schema | null>(null);
  const [v, setV] = useState<Record<string, any>>({});
  const [files, setFiles] = useState<Record<string, ImagePicker.ImagePickerAsset>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [pledge, setPledge] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pick, setPick] = useState<F | null>(null);
  const [date, setDate] = useState<F | null>(null);

  useEffect(() => {
    api<Schema>(`/pubs/${key}/form/${id ? `?id=${id}` : ''}`).then((r) => {
      setS(r);
      const init: Record<string, any> = {};
      for (const f of r.fields) if (f.value !== undefined && f.kind !== 'image' && f.kind !== 'file') init[f.name] = f.value;
      setV(init);
    }).catch((e) => Alert.alert(e.message));
  }, [key, id]);

  if (!s) return <Screen back title=""><Loading /></Screen>;

  const set = (name: string, val: any) => {
    setV((o) => ({ ...o, [name]: val }));
    setErrors((e) => ({ ...e, [name]: '' }));
  };
  const gps = async () => {
    const perm = await Location.requestForegroundPermissionsAsync();
    if (!perm.granted) return Alert.alert(t('Нет доступа к геолокации'));
    const p = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
    set('lat', p.coords.latitude.toFixed(6));
    set('lon', p.coords.longitude.toFixed(6));
  };
  const image = async (name: string) => {
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.85, allowsEditing: true });
    if (!r.canceled && r.assets[0]) setFiles((o) => ({ ...o, [name]: r.assets[0] }));
  };

  const submit = async () => {
    setBusy(true);
    setErrors({});
    try {
      const form = new FormData();
      if (id) form.append('id', String(id));
      if (!s.editing) form.append('pledge', pledge ? '1' : '');
      for (const f of s.fields) {
        if (f.kind === 'image' || f.kind === 'file') continue;
        const val = v[f.name];
        if (f.kind === 'bool') { if (val) form.append(f.name, 'on'); continue; }
        if (val !== undefined && val !== null && val !== '') form.append(f.name, String(val));
      }
      for (const [name, a] of Object.entries(files)) form.append(name, { uri: a.uri, name: a.fileName || 'photo.jpg', type: a.mimeType || 'image/jpeg' } as any);
      const r = await api(`/pubs/${key}/save/`, { form, timeout: 60000 });
      Alert.alert(r.message);
      router.back();
    } catch (e) {
      const err = e as ApiError;
      setErrors({ ...err.fields, all: err.message });
      if (err.code === 'money') Alert.alert(err.message, undefined, [{ text: t('Пополнить'), onPress: () => openWeb('/wallet/topup/') }, { text: 'OK' }]);
    } finally {
      setBusy(false);
    }
  };

  const geoDone = v.lat && v.lon;
  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen back title={s.editing ? t('Изменить') : s.title}>
        {s.editing ? <Txt kind="small">{t('После правки публикация снова пройдёт проверку модератором.')}</Txt> : null}
        {s.price ? <Card soft><Txt>{t('Публикация платная: {p} сум с баланса.', { p: s.price.toLocaleString('ru-RU') })}</Txt></Card> : null}
        {s.fields.map((f) => {
          if (f.name === 'lon' && s.geo) return null;
          if (f.name === 'lat' && s.geo) {
            return (
              <View key="geo" style={{ gap: 8 }}>
                <Txt kind="small" style={{ fontWeight: '600', color: c.ink }}>{t('Место на карте')} *</Txt>
                <Button kind={geoDone ? 'soft' : 'ghost'} icon="navigate" title={geoDone ? `✓ ${Number(v.lat).toFixed(4)}, ${Number(v.lon).toFixed(4)}` : t('Я сейчас здесь — взять по GPS')} onPress={gps} />
                {errors.lat || errors.lon ? <Txt kind="small" color={c.bad}>{errors.lat || errors.lon}</Txt> : null}
              </View>
            );
          }
          const label = `${f.label}${f.required ? ' *' : ''}`;
          if (f.kind === 'text' || f.kind === 'line' || f.kind === 'url' || f.kind === 'number') {
            return <Field key={f.name} label={label} value={v[f.name] === undefined ? '' : String(v[f.name])} onChangeText={(x) => set(f.name, x)}
              multiline={f.kind === 'text'} maxLength={f.max_length ?? undefined} error={errors[f.name]}
              keyboardType={f.kind === 'number' ? 'decimal-pad' : f.kind === 'url' ? 'url' : 'default'} autoCapitalize={f.kind === 'url' ? 'none' : 'sentences'}
              placeholder={f.help || undefined} />;
          }
          if (f.kind === 'bool') {
            return (
              <View key={f.name} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <Txt style={{ flex: 1 }}>{f.label}</Txt>
                <Switch value={!!v[f.name]} onValueChange={(x) => set(f.name, x)} trackColor={{ true: c.accent, false: c.line }} />
              </View>
            );
          }
          if (f.kind === 'choice') {
            const cur = f.choices?.find((x) => String(x.key) === String(v[f.name] ?? ''));
            const few = (f.choices?.length ?? 0) <= 6;
            return (
              <View key={f.name} style={{ gap: 6 }}>
                <Txt kind="small" style={{ fontWeight: '600', color: c.ink }}>{label}</Txt>
                {few ? (
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                    {f.choices!.map((x) => <Chip key={String(x.key)} label={x.name} on={cur?.key === x.key} onPress={() => set(f.name, x.key)} />)}
                  </View>
                ) : (
                  <Pressable onPress={() => setPick(f)} style={{ backgroundColor: c.card2, borderRadius: 16, padding: 14, flexDirection: 'row', borderWidth: 1, borderColor: errors[f.name] ? c.bad : c.line }}>
                    <Txt style={{ flex: 1 }} color={cur ? c.ink : c.inkSoft}>{cur?.name ?? t('Выбрать')}</Txt>
                    <Icon name="chevron-down" size={18} color={c.inkSoft} />
                  </Pressable>
                )}
                {errors[f.name] ? <Txt kind="small" color={c.bad}>{errors[f.name]}</Txt> : null}
              </View>
            );
          }
          if (f.kind === 'date') {
            return (
              <View key={f.name} style={{ gap: 6 }}>
                <Txt kind="small" style={{ fontWeight: '600', color: c.ink }}>{label}</Txt>
                <Pressable onPress={() => setDate(f)} style={{ backgroundColor: c.card2, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: c.line }}>
                  <Txt color={v[f.name] ? c.ink : c.inkSoft}>{v[f.name] ? String(v[f.name]).split('-').reverse().join('.') : t('Выбрать дату')}</Txt>
                </Pressable>
              </View>
            );
          }
          if (f.kind === 'image') {
            const uri = files[f.name]?.uri ?? f.value;
            return (
              <Pressable key={f.name} onPress={() => image(f.name)} style={{ alignItems: 'center', gap: 8, padding: 14, borderRadius: 18, borderWidth: 1.5, borderStyle: 'dashed', borderColor: c.accent }}>
                {uri ? <Image source={{ uri }} style={{ width: 160, height: 120, borderRadius: 12 }} contentFit="cover" /> : <Icon name="image-outline" size={34} color={c.accent} />}
                <Txt color={c.accent} style={{ fontWeight: '700' }}>{uri ? t('Заменить фото') : f.label}</Txt>
                {errors[f.name] ? <Txt kind="small" color={c.bad}>{errors[f.name]}</Txt> : null}
              </Pressable>
            );
          }
          return null;
        })}
        {!s.editing ? (
          <Card style={{ gap: 8 }}>
            <Txt kind="h3">🤝 {t('Договор перед Аллахом')}</Txt>
            <Txt kind="small" style={{ fontStyle: 'italic' }}>{t('«…И будьте верны договору, ибо за договор спросят»')} — {t('Коран, сура «аль-Исра», 17:34')}</Txt>
            {s.pledge.map((p) => <Txt key={p} kind="small" style={{ color: c.ink }}>• {p}</Txt>)}
            <Row title={t('Боюсь Аллаха, обязуюсь соблюдать договор и отвечаю за свою публикацию')} onPress={() => setPledge(!pledge)}
              right={<Icon name={pledge ? 'checkbox' : 'square-outline'} color={c.accent} />} />
          </Card>
        ) : null}
        {errors.all ? <Txt color={c.bad}>{errors.all}</Txt> : null}
        <Button title={s.editing ? t('Сохранить') : t('Опубликовать')} onPress={submit} loading={busy} disabled={!s.editing && !pledge} />

        <Modal visible={!!pick} animationType="slide" transparent onRequestClose={() => setPick(null)}>
          <Pressable style={{ flex: 1, backgroundColor: c.overlay }} onPress={() => setPick(null)} />
          <View style={{ backgroundColor: c.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '70%', padding: 16 }}>
            <Txt kind="h3" style={{ marginBottom: 10 }}>{pick?.label}</Txt>
            <ScrollView>
              {pick ? <OptionList options={pick.choices ?? []} value={v[pick.name]} onChange={(x) => { set(pick.name, x); setPick(null); }} /> : null}
            </ScrollView>
          </View>
        </Modal>
        {date ? (
          <DateTimePicker value={v[date.name] ? new Date(v[date.name]) : new Date()} mode="date" minimumDate={new Date()}
            onChange={(e, d) => { const f = date; setDate(null); if (e.type === 'set' && d) set(f.name, d.toISOString().slice(0, 10)); }} />
        ) : null}
      </Screen>
    </KeyboardAvoidingView>
  );
}
