import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, Pressable, TextInput, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp, type Privacy, type SocialLink, type User } from '@/state/app';
import { Avatar, Button, Field, Icon, Screen, Section, Segmented, Sheet, Txt } from '@/ui/kit';
import { useAvatarPick } from '@/ui/photo-editor';
import { privacyName, SOCIAL } from '@/ui/profile';

type Link = { kind: string; value: string; privacy: Privacy };

/** Правка профиля: фото, имя, @имя пользователя, «о себе», город и соцсети (у каждой — кто её видит). */
export default function ProfileEdit() {
  const { c, t, user, setUser } = useApp();
  const [first, setFirst] = useState(user?.first_name ?? '');
  const [last, setLast] = useState(user?.last_name ?? '');
  const [handle, setHandle] = useState(user?.handle ?? '');
  const [bio, setBio] = useState(user?.bio ?? '');
  const [city, setCity] = useState(user?.city ?? '');
  const [links, setLinks] = useState<Link[]>((user?.links ?? []).map((l) => ({ kind: l.kind, value: l.value, privacy: l.privacy ?? 'all' })));
  const [photo, setPhoto] = useState<{ uri: string } | null>(null);
  const [view, setView] = useState(user?.links_mode ?? 'auto');
  const avatarPick = useAvatarPick((uri) => setPhoto({ uri }));
  const [busy, setBusy] = useState(false);
  const [pick, setPick] = useState<{ row: number; what: 'kind' | 'privacy' } | null>(null);
  if (!user) return null;

  const pickPhoto = avatarPick.pick;               // своя обрезка как в Telegram: рамка-квадрат с кругом
  const setLink = (i: number, part: Partial<Link>) => setLinks((old) => old.map((l, n) => (n === i ? { ...l, ...part } : l)));
  const kindName = (k: string) => (k === 'website' ? t('Сайт') : k === 'other' ? t('Другое') : SOCIAL.find((x) => x.key === k)?.name ?? k);

  const save = async () => {
    setBusy(true);
    try {
      const form = new FormData();
      form.append('first_name', first);
      form.append('last_name', last);
      form.append('handle', handle);
      form.append('bio', bio);
      form.append('city', city);
      if (photo) form.append('avatar', { uri: photo.uri, name: 'avatar.jpg', type: 'image/jpeg' } as any);
      const me = await api<User>('/me/', { form });
      const r = await api<{ links: SocialLink[]; links_view: string; links_mode: string }>('/me/links/', { body: { links: links.filter((l) => l.value.trim()), view } });
      setUser({ ...me, links: r.links, links_view: r.links_view, links_mode: r.links_mode });
      router.back();
    } catch (e) {
      Alert.alert((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  const row = pick ? links[pick.row] : null;
  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen title={t('Профиль')} back>
        <Pressable onPress={pickPhoto} style={{ alignItems: 'center', gap: 8 }}>
          <Avatar uri={photo?.uri ?? user.avatar} name={user.name} size={104} hue={user.id} />
          <Txt kind="small" color={c.accent} style={{ fontWeight: '700' }}>{t('Сменить фото')}</Txt>
        </Pressable>
        <Field label={t('Имя')} value={first} onChangeText={setFirst} maxLength={150} />
        <Field label={t('Фамилия (необязательно)')} value={last} onChangeText={setLast} maxLength={150} />
        <View style={{ gap: 4 }}>
          <Field label={t('Имя пользователя')} value={handle} onChangeText={(x) => setHandle(x.replace(/^@/, '').toLowerCase())} maxLength={32}
            autoCapitalize="none" autoCorrect={false} placeholder="ali_2024" />
          <Txt kind="small">{t('По нему вас находят в поиске: @имя. Латинские буквы, цифры и «_», от 4 знаков, первая — буква.')}</Txt>
        </View>
        <Field label={t('О себе')} value={bio} onChangeText={setBio} maxLength={160} placeholder={t('Пара слов о себе')} />
        <Field label={t('Город')} value={city} onChangeText={setCity} maxLength={80} />

        <Section title={t('Соцсети и ссылки')}>
          <Txt kind="small">{t('Instagram, Telegram, YouTube, GitHub, Discord — что хотите. Для каждой ссылки выберите, кто её видит.')}</Txt>
          {links.map((l, i) => (
            // одна строка на ссылку: слева значок сети (нажать — сменить сеть), рядом поле, справа — убрать
            <View key={i} style={{ gap: 5 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: c.card2, borderRadius: 14, borderWidth: 1, borderColor: c.line }}>
                <Pressable onPress={() => setPick({ row: i, what: 'kind' })} accessibilityLabel={`${t('Сеть')}: ${kindName(l.kind)}`}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 3, paddingLeft: 12, paddingRight: 8, paddingVertical: 12, borderRightWidth: 1, borderRightColor: c.line }}>
                  <Icon name={SOCIAL.find((x) => x.key === l.kind)?.icon ?? 'link-outline'} size={21} color={c.accent} />
                  <Icon name="chevron-down" size={13} color={c.inkSoft} />
                </Pressable>
                <TextInput value={l.value} onChangeText={(x) => setLink(i, { value: x })} maxLength={120} autoCapitalize="none" autoCorrect={false}
                  placeholder={`${kindName(l.kind)}: ${SOCIAL.find((x) => x.key === l.kind)?.hint || t('имя или ссылка')}`} placeholderTextColor={c.inkSoft}
                  style={{ flex: 1, fontSize: 16, color: c.ink, paddingHorizontal: 12, paddingVertical: 12 }} />
                <Pressable onPress={() => setLinks((old) => old.filter((_x, n) => n !== i))} hitSlop={8} accessibilityLabel={t('Убрать')} style={{ padding: 10 }}>
                  <Icon name="close-circle" size={20} color={c.inkSoft} />
                </Pressable>
              </View>
              <Pressable onPress={() => setPick({ row: i, what: 'privacy' })} hitSlop={6} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 6 }}>
                <Icon name="eye-outline" size={15} color={c.inkSoft} />
                <Txt kind="small">{t('Кто видит')}:</Txt>
                <Txt kind="small" color={c.accent} style={{ fontWeight: '700' }}>{privacyName(l.privacy, t)}</Txt>
              </Pressable>
            </View>
          ))}
          {links.length ? (
            <View style={{ gap: 6 }}>
              <Txt kind="small" style={{ fontWeight: '600', color: c.ink }}>{t('Как показывать ссылки в профиле')}</Txt>
              <Segmented value={view} onChange={setView} options={[{ key: 'auto', label: t('Авто') }, { key: 'icons', label: t('Значками') }, { key: 'list', label: t('Списком') }]} />
              <Txt kind="small">{t('«Авто» — значками в ряд, если ссылок больше двух: профиль не растягивается.')}</Txt>
            </View>
          ) : null}
          {links.length < 12 ? <Button kind="soft" small icon="add" title={t('Добавить ссылку')} onPress={() => { setLinks((old) => [...old, { kind: 'telegram', value: '', privacy: 'all' }]); setPick({ row: links.length, what: 'kind' }); }} /> : null}
        </Section>
        <Button title={t('Сохранить')} onPress={save} loading={busy} />
      </Screen>
      <Sheet open={!!pick && pick.what === 'kind'} onClose={() => setPick(null)} title={t('Сеть')}
        items={SOCIAL.map((x) => ({ icon: x.icon, title: kindName(x.key), on: row?.kind === x.key, onPress: () => pick && setLink(pick.row, { kind: x.key }) }))} />
      <Sheet open={!!pick && pick.what === 'privacy'} onClose={() => setPick(null)} title={t('Кто видит')}
        items={(['all', 'close', 'nobody'] as Privacy[]).map((p) => ({ title: privacyName(p, t), on: row?.privacy === p,
          subtitle: p === 'close' ? t('Только те, кого вы добавили в близкие друзья') : p === 'nobody' ? t('Ссылка сохранена, но никому не показывается') : undefined,
          onPress: () => pick && setLink(pick.row, { privacy: p }) }))} />
      {avatarPick.editor}
    </KeyboardAvoidingView>
  );
}
