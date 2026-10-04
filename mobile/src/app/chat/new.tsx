import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, Switch, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, Field, Icon, Screen, Segmented, Txt } from '@/ui/kit';
import { useAvatarPick } from '@/ui/photo-editor';

/** Новая группа или канал. Те же правила, что на сайте (apps/chat/rooms.py). */
export default function NewRoom() {
  const params = useLocalSearchParams<{ kind?: string }>();
  const { c, t } = useApp();
  const [kind, setKind] = useState<'group' | 'channel'>(params.kind === 'channel' ? 'channel' : 'group');
  const [title, setTitle] = useState('');
  const [about, setAbout] = useState('');
  const [isPublic, setPublic] = useState(false);
  const [handle, setHandle] = useState('');
  const [avatar, setAvatar] = useState<{ uri: string } | null>(null);
  const avatarPick = useAvatarPick((uri) => setAvatar({ uri }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const pick = avatarPick.pick;
  const create = async () => {
    setBusy(true);
    setError('');
    try {
      const form = new FormData();
      form.append('kind', kind);
      form.append('title', title);
      form.append('about', about);
      if (isPublic) form.append('is_public', '1');
      form.append('handle', isPublic ? handle : '');
      if (avatar) form.append('avatar', { uri: avatar.uri, name: 'avatar.jpg', type: 'image/jpeg' } as any);
      const r = await api<{ thread: number }>('/chat/rooms/new/', { form, timeout: 60000 });
      router.replace(`/chat/${r.thread}`);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen back title={kind === 'channel' ? t('Новый канал') : t('Новая группа')}>
        <Segmented value={kind} onChange={setKind} options={[{ key: 'group', label: t('Группа') }, { key: 'channel', label: t('Канал') }]} />
        <Txt kind="muted">{kind === 'channel'
          ? t('Канал — это лента: пишете вы и ваши админы, подписчики читают. Подходит мечети, учителю, магазину.')
          : t('Группа — общий чат: пишут все участники. Семья, община, однокурсники, соседи.')}</Txt>
        <Pressable onPress={pick} style={{ alignSelf: 'center', alignItems: 'center', gap: 6 }}>
          {avatar ? <Image source={{ uri: avatar.uri }} style={{ width: 92, height: 92, borderRadius: 30 }} contentFit="cover" />
            : <View style={{ width: 92, height: 92, borderRadius: 30, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}><Icon name="camera-outline" size={32} color={c.accent} /></View>}
          <Txt kind="small" color={c.accent} style={{ fontWeight: '700' }}>{avatar ? t('Заменить фото') : t('Картинка (необязательно)')}</Txt>
        </Pressable>
        <Field label={`${t('Название')} *`} value={title} onChangeText={setTitle} maxLength={120}
          placeholder={kind === 'channel' ? t('Например: Мечеть «Нур» — объявления') : t('Например: Община Ташкента')} />
        <Field label={t('Описание')} value={about} onChangeText={setAbout} maxLength={500} multiline placeholder={t('О чём этот чат, для кого он')} />
        <Card soft style={{ gap: 10 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <Txt style={{ flex: 1, fontWeight: '600' }}>{t('Виден в каталоге, вступить может любой')}</Txt>
            <Switch value={isPublic} onValueChange={setPublic} trackColor={{ true: c.accent, false: c.line }} />
          </View>
          {isPublic ? (
            <Field label={t('Публичное имя')} value={handle} onChangeText={(x) => setHandle(x.toLowerCase())} maxLength={32} autoCapitalize="none"
              autoCorrect={false} placeholder="masjid_nur" />
          ) : <Txt kind="small">{t('Без галочки попасть можно только по вашей ссылке-приглашению.')}</Txt>}
          {isPublic ? <Txt kind="small">{t('Латинские буквы (a–z), цифры и «_», от 3 знаков. Например: masjid_nur или ilm2024. По этому адресу чат находят и делятся им.')}</Txt> : null}
        </Card>
        {error ? <Txt color={c.bad}>{error}</Txt> : null}
        <Button title={t('Создать')} icon="add" onPress={create} loading={busy} disabled={title.trim().length < 2} />
      </Screen>
      {avatarPick.editor}
    </KeyboardAvoidingView>
  );
}
