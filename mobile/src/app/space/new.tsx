import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, Switch, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, Field, Icon, Screen, Txt } from '@/ui/kit';
import { useAvatarPick } from '@/ui/photo-editor';

/** Новое сообщество. Сразу появляются каналы «объявления» и «общий» — те же правила, что на сайте (apps/chat/spaces.py). */
export default function NewSpace() {
  const { c, t } = useApp();
  const [title, setTitle] = useState('');
  const [about, setAbout] = useState('');
  const [isPublic, setPublic] = useState(true);
  const [icon, setIcon] = useState<{ uri: string } | null>(null);
  const pick = useAvatarPick((uri) => setIcon({ uri }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const create = async () => {
    setBusy(true);
    setError('');
    try {
      const form = new FormData();
      form.append('title', title);
      form.append('about', about);
      if (isPublic) form.append('is_public', '1');
      if (icon) form.append('icon', { uri: icon.uri, name: 'icon.jpg', type: 'image/jpeg' } as any);
      const r = await api<{ id: number }>('/communities/new/', { form, timeout: 60000 });
      router.replace(`/space/${r.id}`);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen back title={t('Новое сообщество')}>
        <Txt kind="muted">{t('Сообщество — это место для своих: несколько каналов по темам, объявления, роли. Сразу появятся каналы «объявления» и «общий» — остальные добавите сами.')}</Txt>
        <Pressable onPress={pick.pick} style={{ alignSelf: 'center', alignItems: 'center', gap: 6 }}>
          {icon ? <Image source={{ uri: icon.uri }} style={{ width: 92, height: 92, borderRadius: 46 }} contentFit="cover" />
            : <View style={{ width: 92, height: 92, borderRadius: 46, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}><Icon name="camera-outline" size={32} color={c.accent} /></View>}
          <Txt kind="small" color={c.accent} style={{ fontWeight: '700' }}>{icon ? t('Заменить фото') : t('Значок (необязательно)')}</Txt>
        </Pressable>
        <Field label={`${t('Название')} *`} value={title} onChangeText={setTitle} maxLength={80} placeholder={t('Например: Айтишники Ташкента')} />
        <Field label={t('Описание')} value={about} onChangeText={setAbout} maxLength={500} multiline placeholder={t('О чём сообщество, для кого оно')} />
        <Card soft style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <View style={{ flex: 1 }}>
            <Txt style={{ fontWeight: '700' }}>{t('Открытое: видно в каталоге, вступить может любой')}</Txt>
            <Txt kind="small">{t('Без галочки попасть можно только по вашей ссылке-приглашению.')}</Txt>
          </View>
          <Switch value={isPublic} onValueChange={setPublic} trackColor={{ true: c.accent }} />
        </Card>
        {error ? <Txt color={c.bad}>{error}</Txt> : null}
        <Button title={t('Создать сообщество')} icon="add" onPress={create} loading={busy} disabled={title.trim().length < 2} />
      </Screen>
      {pick.editor}
    </KeyboardAvoidingView>
  );
}
