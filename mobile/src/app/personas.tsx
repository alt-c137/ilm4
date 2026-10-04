import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Switch, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Button, Card, Field, Loading, Press, Screen, Section, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type P = { name: string; avatar: string; link_main: boolean } | null;
type Data = { items: { board: P; spaces: P }; nikah: { name: string; published: boolean } | null; main: { name: string; handle: string; avatar: string } };
type Sec = 'board' | 'spaces';

/**
 * «Мои профили» — маски. Аккаунт один, но в объявлениях и в сообществах можно выступать под другим именем:
 * по одному профилю на раздел. Никях — отдельная анкета.
 */
export default function Personas() {
  const { c, t, moduleOn, user } = useApp();
  const { data, setData, loading } = useFetch<Data>(user ? '/me/personas/' : null);
  const [draft, setDraft] = useState<Record<Sec, { name: string; link: boolean; photo: string } | undefined>>({ board: undefined, spaces: undefined });
  const [busy, setBusy] = useState<Sec | null>(null);
  if (!user) return null;
  if (!data) return <Screen title={t('Мои профили')} back>{loading ? <Loading /> : null}</Screen>;

  const value = (s: Sec) => draft[s] ?? { name: data.items[s]?.name ?? '', link: data.items[s]?.link_main ?? true, photo: '' };
  const edit = (s: Sec, part: Partial<{ name: string; link: boolean; photo: string }>) => setDraft((old) => ({ ...old, [s]: { ...value(s), ...part } }));
  const pick = async (s: Sec) => {
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, aspect: [1, 1], quality: 0.85 });
    if (!r.canceled && r.assets[0]) edit(s, { photo: r.assets[0].uri });
  };
  const save = async (s: Sec, remove = false) => {
    const v = value(s);
    setBusy(s);
    try {
      const form = new FormData();
      form.append('section', s);
      form.append('name', remove ? '' : v.name);
      form.append('link_main', s === 'board' && !v.link ? '0' : '1');
      if (v.photo && !remove) form.append('avatar', { uri: v.photo, name: 'avatar.jpg', type: 'image/jpeg' } as any);
      setData(await api<Data>('/me/personas/', { form }));
      setDraft((old) => ({ ...old, [s]: undefined }));
    } catch (e) {
      Alert.alert((e as ApiError).message);
    } finally {
      setBusy(null);
    }
  };

  const block = (s: Sec, title: string, hint: string) => {
    const v = value(s);
    const saved = data.items[s];
    return (
      <Section title={title}>
        <Card style={{ gap: 12 }}>
          <Txt kind="small">{hint}</Txt>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            <Press onPress={() => pick(s)}>
              <Avatar uri={v.photo || saved?.avatar} name={v.name || data.main.name} size={52} hue={s === 'board' ? 3 : 5} />
            </Press>
            <View style={{ flex: 1 }}>
              <Field value={v.name} onChangeText={(x) => edit(s, { name: x })} maxLength={40} placeholder={data.main.name} />
            </View>
          </View>
          {s === 'board' ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Txt style={{ fontWeight: '600' }}>{t('Показывать ссылку на основной профиль')}</Txt>
                <Txt kind="small">{t('Выключите — и покупатель увидит только это имя: без @имени, ленты и подписчиков.')}</Txt>
              </View>
              <Switch value={v.link} onValueChange={(x) => edit(s, { link: x })} trackColor={{ true: c.accent, false: c.line }} />
            </View>
          ) : null}
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button small title={t('Сохранить')} onPress={() => save(s)} loading={busy === s} disabled={v.name.trim().length < 2} style={{ flex: 1 }} />
            {saved ? <Button small kind="soft" title={t('Убрать')} onPress={() => save(s, true)} style={{ flex: 1 }} /> : null}
          </View>
          {!saved ? <Txt kind="small">{t('Сейчас здесь виден основной профиль.')}</Txt> : null}
        </Card>
      </Section>
    );
  };

  return (
    <Screen title={t('Мои профили')} back>
      <Txt kind="muted">{t('Аккаунт один — один вход и один номер. Но в разных разделах вас могут видеть по-разному: по одному профилю на раздел.')}</Txt>
      <Section title={t('Основной профиль')}>
        <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }} onPress={() => router.push('/profile-edit')}>
          <Avatar uri={data.main.avatar} name={data.main.name} size={52} hue={user.id} />
          <View style={{ flex: 1 }}>
            <Txt style={{ fontWeight: '700', fontSize: 16 }}>{data.main.name}</Txt>
            <Txt kind="small">{t('Чаты и лента')}{data.main.handle ? ` · @${data.main.handle}` : ''}</Txt>
          </View>
        </Card>
      </Section>
      {block('board', t('Объявления, работа, услуги'), t('Под этим именем вас видят в объявлениях, вакансиях и в чатах по ним.'))}
      {moduleOn('communities') ? block('spaces', t('Сообщества'), t('Ваше имя во всех сообществах. В отдельном сообществе можно поставить свой ник — он важнее.')) : null}
      {moduleOn('nikah') ? (
        <Section title={t('Никях')}>
          <Card style={{ gap: 4 }} onPress={() => router.push('/nikah')}>
            <Txt style={{ fontWeight: '700', fontSize: 16 }}>{data.nikah ? data.nikah.name : t('Анкеты пока нет')}</Txt>
            <Txt kind="small">{t('Отдельная анкета: по профилю и объявлениям о ней не узнать, в чате никяха видно только имя из анкеты')}</Txt>
          </Card>
        </Section>
      ) : null}
    </Screen>
  );
}
