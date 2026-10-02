import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable } from 'react-native';

import { api } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Button, Field, Screen, Txt } from '@/ui/kit';

export default function ProfileEdit() {
  const { c, t, user, setUser } = useApp();
  const [first, setFirst] = useState(user?.first_name ?? '');
  const [nick, setNick] = useState(user?.nickname ?? '');
  const [city, setCity] = useState(user?.city ?? '');
  const [photo, setPhoto] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [busy, setBusy] = useState(false);
  if (!user) return null;

  const pick = async () => {
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, aspect: [1, 1], quality: 0.8 });
    if (!r.canceled && r.assets[0]) setPhoto(r.assets[0]);
  };
  const save = async () => {
    setBusy(true);
    try {
      const form = new FormData();
      form.append('first_name', first);
      form.append('nickname', nick);
      form.append('city', city);
      if (photo) form.append('avatar', { uri: photo.uri, name: photo.fileName || 'avatar.jpg', type: photo.mimeType || 'image/jpeg' } as any);
      setUser(await api('/me/', { form }));
      router.back();
    } catch (e: any) {
      Alert.alert(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen title={t('Профиль')} back>
      <Pressable onPress={pick} style={{ alignItems: 'center', gap: 8 }}>
        <Avatar uri={photo?.uri ?? user.avatar} name={user.name} size={96} hue={user.id} />
        <Txt kind="small" color={c.accent}>{t('Сменить фото')}</Txt>
      </Pressable>
      <Field label={t('Имя')} value={first} onChangeText={setFirst} />
      <Field label={t('Ник')} value={nick} onChangeText={setNick} />
      <Field label={t('Город')} value={city} onChangeText={setCity} />
      <Button title={t('Сохранить')} onPress={save} loading={busy} />
    </Screen>
  );
}
