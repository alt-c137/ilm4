import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, ScrollView, TextInput, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Button, Icon, Screen, Sheet, Txt } from '@/ui/kit';

/** Новая запись на стене: текст, до 10 фото, кто видит (все или близкие друзья). */
export default function NewPost() {
  const { c, t, user } = useApp();
  const [text, setText] = useState('');
  const [photos, setPhotos] = useState<ImagePicker.ImagePickerAsset[]>([]);
  const [privacy, setPrivacy] = useState<'all' | 'close'>('all');
  const [pick, setPick] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!user) return null;
  const add = async () => {
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsMultipleSelection: true, selectionLimit: 10 - photos.length, quality: 0.85 });
    if (!r.canceled) setPhotos((old) => [...old, ...r.assets].slice(0, 10));
  };
  const send = async () => {
    setBusy(true);
    try {
      const form = new FormData();
      form.append('text', text);
      form.append('privacy', privacy);
      photos.forEach((a, i) => form.append('photos', { uri: a.uri, name: a.fileName || `photo${i}.jpg`, type: a.mimeType || 'image/jpeg' } as any));
      await api('/feed/new/', { form, timeout: 120000 });
      router.back();
    } catch (e) {
      Alert.alert((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen title={t('Новая запись')} back
      right={<Button small title={t('Опубликовать')} loading={busy} disabled={!text.trim() && !photos.length} onPress={send} />}>
      <View style={{ flexDirection: 'row', gap: 12 }}>
        <Avatar uri={user.avatar} name={user.name} size={42} hue={user.id} />
        <TextInput value={text} onChangeText={setText} placeholder={t('Что у вас нового?')} placeholderTextColor={c.inkSoft} multiline autoFocus maxLength={4000}
          style={{ flex: 1, minHeight: 120, fontSize: 17, lineHeight: 24, color: c.ink, textAlignVertical: 'top', paddingTop: 8 }} />
      </View>
      {photos.length ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          {photos.map((p, i) => (
            <View key={p.uri}>
              <Image source={{ uri: p.uri }} style={{ width: 96, height: 96, borderRadius: 14 }} contentFit="cover" />
              <Pressable onPress={() => setPhotos((old) => old.filter((_x, n) => n !== i))} hitSlop={8}
                style={{ position: 'absolute', right: 4, top: 4, width: 24, height: 24, borderRadius: 12, backgroundColor: 'rgba(0,0,0,0.55)', alignItems: 'center', justifyContent: 'center' }}>
                <Icon name="close" size={15} color="#fff" />
              </Pressable>
            </View>
          ))}
        </ScrollView>
      ) : null}
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <Button kind="soft" icon="images" title={t('Фото')} onPress={add} disabled={photos.length >= 10} style={{ flex: 1 }} />
        <Button kind="soft" icon={privacy === 'all' ? 'earth' : 'heart'} title={privacy === 'all' ? t('Видят все') : t('Близкие друзья')} onPress={() => setPick(true)} style={{ flex: 1 }} />
      </View>
      <Txt kind="small">{t('До 10 фото. «Близкие друзья» — запись увидят только те, кого вы добавили в близкие.')}</Txt>
      <Sheet open={pick} onClose={() => setPick(false)} title={t('Кто видит')} items={[
        { icon: 'earth-outline', title: t('Видят все'), on: privacy === 'all', onPress: () => setPrivacy('all') },
        { icon: 'heart-outline', title: t('Только близкие друзья'), on: privacy === 'close', onPress: () => setPrivacy('close') },
      ]} />
    </Screen>
  );
}
