import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { openWeb } from '@/lib/links';
import { useApp } from '@/state/app';
import { Button, Card, Icon, Screen, SetGroup, SetRow, Txt } from '@/ui/kit';
import { useAvatarPick } from '@/ui/photo-editor';
import { PhotoViewer, type Photo } from '@/ui/photo-viewer';
import { ProfileActions, ProfileHead, ProfileInfo } from '@/ui/profile';

/**
 * Вкладка «Профиль» — как в Telegram: аватар и имя, «Мой профиль», своё (избранное, сохранённое, публикации),
 * одна строка «Настройки» — всё, что настраивается, лежит внутри неё по блокам.
 */
type Photos = { items: Photo[]; avatar: string };

export default function Me() {
  const { c, t, user, signOut, moduleOn, refreshMe } = useApp();
  // свои фото профиля — как в Telegram: нажал на аватар — листаешь все; можно сделать главным, удалить, добавить
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [viewer, setViewer] = useState<number | null>(null);
  const applyPhotos = (r: Photos) => { setPhotos(r.items); refreshMe(); };
  const openPhotos = async () => {
    try {
      const r = await api<Photos>('/me/photos/');
      setPhotos(r.items);
      if (r.items.length) setViewer(0); else addPhoto();
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const avatarPick = useAvatarPick(async (uri) => {
    const form = new FormData();
    form.append('photo', { uri, name: 'avatar.jpg', type: 'image/jpeg' } as any);
    try {
      applyPhotos(await api<Photos>('/me/photos/', { form }));
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  });
  const addPhoto = avatarPick.pick;
  const photoAct = async (body: Record<string, unknown>) => {
    try {
      const r = await api<Photos>('/me/photos/', { body });
      applyPhotos(r);
      setViewer(r.items.length ? 0 : null);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const openSaved = async () => {
    try {
      const r = await api<{ thread: number }>('/chat/saved/', { body: {} });
      router.push(`/chat/${r.thread}`);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  return (
    <Screen onRefresh={user ? refreshMe : undefined}>
      {user ? (
        <>
          <ProfileHead name={user.name} avatar={user.avatar} hue={user.id} verified={user.verified} status={t('в сети')} online
            onAvatar={openPhotos} onCamera={addPhoto} />
          <ProfileActions items={[
            { icon: 'pencil-outline', label: t('Изменить'), onPress: () => router.push('/profile-edit') },
            { icon: 'eye-outline', label: t('Как видят'), onPress: () => router.push(`/user/${user.id}`) },
            { icon: 'settings-outline', label: t('Настройки'), onPress: () => router.push('/settings') },
          ]} />
          <ProfileInfo mine phone={user.phone} phonePrivacy={user.privacy?.phone} handle={user.handle} bio={user.bio} city={user.city}
            links={user.links} linksView={user.links_view} onSetHandle={() => router.push('/profile-edit')} />
        </>
      ) : (
        <Card style={{ gap: 12, alignItems: 'center', marginTop: 12 }}>
          <Icon name="person-circle-outline" size={56} color={c.accent} />
          <Txt kind="h3" style={{ textAlign: 'center' }}>{t('Войдите, чтобы писать, откликаться и знакомиться в никяхе')}</Txt>
          <Button title={t('Войти или зарегистрироваться')} onPress={() => router.push('/login')} style={{ alignSelf: 'stretch' }} />
        </Card>
      )}

      {user && user.balance !== null && moduleOn('wallet') ? (
        <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }} onPress={() => router.push('/wallet')}>
          <View style={{ flex: 1 }}>
            <Txt kind="label">{t('Баланс')}</Txt>
            <Txt kind="h2">{user.balance.toLocaleString('ru-RU')} {t('сум')}</Txt>
          </View>
          <Button small title={t('Пополнить')} icon="add" onPress={() => openWeb('/wallet/topup/')} />
        </Card>
      ) : null}

      {user ? (
        <SetGroup>
          {moduleOn('chat') ? <SetRow tint="#3b82f6" icon="bookmark" title={t('Избранное')} subtitle={t('Заметки и пересланное')} onPress={openSaved} /> : null}
          {moduleOn('feed') ? <SetRow tint="#f59e0b" icon="bookmarks" title={t('Сохранённое')} subtitle={t('Отложенные записи и объявления')} onPress={() => router.push('/feed/saved')} /> : null}
          <SetRow tint="#10b981" icon="document-text" title={t('Мои публикации')} subtitle={t('Объявления, вакансии, услуги')} onPress={() => router.push('/my')} />
          <SetRow tint="#ef4444" icon="notifications" title={t('Уведомления')} onPress={() => router.push('/notifications')} />
        </SetGroup>
      ) : null}

      <SetGroup>
        <SetRow tint="#64748b" icon="settings" title={t('Настройки')} subtitle={t('Аккаунт, приватность, чаты, язык')} onPress={() => router.push('/settings')} />
      </SetGroup>

      <SetGroup>
        <SetRow tint="#ec4899" icon="heart" title={t('Поддержать проект')} subtitle={t('Садака на развитие ilm4')} onPress={() => openWeb('/support/', false)} />
        <SetRow tint="#f59e0b" icon="star" title={t('Как принять ислам')} onPress={() => openWeb('/islam/', false)} />
      </SetGroup>

      {avatarPick.editor}
      <PhotoViewer photos={photos} index={viewer} onClose={() => setViewer(null)} title={user?.name} actions={[
        { title: t('Сделать главным'), show: (i) => i > 0, onPress: (p) => photoAct({ main: p.id }) },
        { title: t('Новое фото'), onPress: () => { setViewer(null); addPhoto(); } },
        { title: t('Удалить'), danger: true, onPress: (p) => Alert.alert(t('Удалить это фото?'), undefined, [
          { text: t('Отмена'), style: 'cancel' }, { text: t('Удалить'), style: 'destructive', onPress: () => photoAct({ delete: p.id }) }]) },
      ]} />
      {user ? (
        <Pressable onPress={() => Alert.alert(t('Выйти из аккаунта?'), undefined, [
          { text: t('Отмена'), style: 'cancel' }, { text: t('Выйти'), style: 'destructive', onPress: signOut }])}
          style={{ alignItems: 'center', padding: 12 }}>
          <Txt kind="h3" color={c.bad}>{t('Выйти')}</Txt>
        </Pressable>
      ) : null}
    </Screen>
  );
}
