import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, View } from 'react-native';

import { api, ApiError } from '@/lib/api';

import { openWeb } from '@/lib/links';
import { useApp } from '@/state/app';
import { Button, Card, Divider, Icon, Screen, Sheet, Txt, type IconName } from '@/ui/kit';
import { useAvatarPick } from '@/ui/photo-editor';
import { PhotoViewer, type Photo } from '@/ui/photo-viewer';
import { ProfileActions, ProfileHead, ProfileInfo } from '@/ui/profile';

function SetRow({ tint, icon, title, subtitle, onPress }: { tint: string; icon: IconName; title: string; subtitle?: string; onPress: () => void }) {
  const { c } = useApp();
  return (
    <Pressable onPress={onPress} style={({ pressed }) => ({ flexDirection: 'row', alignItems: 'center', gap: 13, paddingVertical: 10, opacity: pressed ? 0.6 : 1 })}>
      <View style={{ width: 34, height: 34, borderRadius: 10, backgroundColor: tint, alignItems: 'center', justifyContent: 'center' }}>
        <Icon name={icon} size={19} color="#fff" />
      </View>
      <View style={{ flex: 1 }}>
        <Txt style={{ fontSize: 16, fontWeight: '600' }}>{title}</Txt>
        {subtitle ? <Txt kind="small" numberOfLines={1}>{subtitle}</Txt> : null}
      </View>
      <Icon name="chevron-forward" size={17} color={c.inkSoft} />
    </Pressable>
  );
}

/** Вкладка «Профиль» — как в Telegram: аватар и имя по центру, кнопки, сведения, ниже — разделы. */
type Photos = { items: Photo[]; avatar: string };

export default function Me() {
  const { c, t, user, signOut, moduleOn, refreshMe, accounts, switchAccount, canAddAccount } = useApp();
  const [accOpen, setAccOpen] = useState(false);
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
  return (
    <Screen onRefresh={user ? refreshMe : undefined}>
      {user ? (
        <>
          <ProfileHead name={user.name} avatar={user.avatar} hue={user.id} verified={user.verified} status={t('в сети')} online
            onAvatar={openPhotos} onCamera={addPhoto} />
          <ProfileActions items={[
            { icon: 'create-outline', label: t('Изменить'), onPress: () => router.push('/profile-edit') },
            { icon: 'eye-outline', label: t('Как видят'), onPress: () => router.push(`/user/${user.id}`) },
            { icon: 'settings-outline', label: t('Настройки'), onPress: () => router.push('/settings') },
          ]} />
          <ProfileInfo mine phone={user.phone} phonePrivacy={user.privacy?.phone} handle={user.handle} bio={user.bio} city={user.city}
            links={user.links} onSetHandle={() => router.push('/profile-edit')} />
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

      {/* разделы — как в настройках Telegram: цветной значок, название, подпись */}
      <Card style={{ paddingVertical: 4 }}>
        {user && moduleOn('nikah') ? <><SetRow tint="#e0457b" icon="heart" title={t('Никях')} subtitle={user.nikah ? t('Моя анкета, симпатии, пары') : t('Создать анкету')} onPress={() => router.push('/nikah')} /><Divider /></> : null}
        {user && moduleOn('assistant') ? <><SetRow tint="#8b5cf6" icon="sparkles" title={t('ИИ-помощник')} subtitle={t('Найдёт место, подскажет намаз, заведёт привычку и встречу')} onPress={() => router.push('/assistant')} /><Divider /></> : null}
        {user && moduleOn('tracker') ? <><SetRow tint="#10b981" icon="checkmark-circle" title={t('Трекер привычек')} subtitle={t('Привычки и дела на день — одному или вместе')} onPress={() => router.push('/tracker')} /><Divider /></> : null}
        {user ? <><SetRow tint="#f59e0b" icon="document-text" title={t('Мои публикации')} subtitle={t('Объявления, вакансии, услуги')} onPress={() => router.push('/my')} /><Divider /></> : null}
        {user ? <><SetRow tint="#ef4444" icon="notifications" title={t('Уведомления')} onPress={() => router.push('/notifications')} /><Divider /></> : null}
        <SetRow tint="#0ea5e9" icon="moon" title={t('Намаз и азан')} onPress={() => router.push('/prayer-settings')} />
      </Card>

      <Card style={{ paddingVertical: 4 }}>
        <SetRow tint="#6d5efc" icon="apps" title={t('Нижние кнопки')} subtitle={t('Какие разделы держать внизу экрана')} onPress={() => router.push('/tabs-setup')} />
        <Divider />
        <SetRow tint="#14b8a6" icon="image" title={t('Фон чата')} subtitle={t('Узор, цвет или своё фото')} onPress={() => router.push('/chat-look')} />
        {moduleOn('chat') ? <><Divider /><SetRow tint="#f59e0b" icon="folder-open" title={t('Папки с чатами')} subtitle={t('Свои вкладки над списком чатов')} onPress={() => router.push('/chat/folders')} /></> : null}
        <Divider />
        {user ? <><SetRow tint="#0ea5e9" icon="people-circle" title={t('Аккаунты')} subtitle={accounts.length > 1 ? t('На устройстве: {n}', { n: accounts.length }) : t('Добавить ещё один и переключаться без выхода')} onPress={() => setAccOpen(true)} /><Divider /></> : null}
        {user ? <><SetRow tint="#22c55e" icon="key" title={t('Приватность')} subtitle={t('Номер, время в сети, близкие друзья')} onPress={() => router.push('/privacy')} /><Divider /></> : null}
        <SetRow tint="#64748b" icon="settings" title={t('Настройки')} subtitle={t('Язык, тема, валюта, аккаунт')} onPress={() => router.push('/settings')} />
      </Card>

      <Card style={{ paddingVertical: 4 }}>
        <SetRow tint="#ec4899" icon="heart-circle" title={t('Поддержать проект')} subtitle={t('Садака на развитие ilm4')} onPress={() => openWeb('/support/', false)} />
        <Divider />
        <SetRow tint="#8b5cf6" icon="shield-checkmark" title={t('Правила')} onPress={() => openWeb('/rules/', false)} />
        <Divider />
        <SetRow tint="#475569" icon="lock-closed" title={t('Политика конфиденциальности')} onPress={() => openWeb('/privacy/', false)} />
        <Divider />
        <SetRow tint="#f59e0b" icon="star" title={t('Как принять ислам')} onPress={() => openWeb('/islam/', false)} />
      </Card>

      {avatarPick.editor}
      <Sheet open={accOpen} onClose={() => setAccOpen(false)} title={t('Аккаунты')} items={[
        ...accounts.map((a) => ({ icon: 'person-circle-outline' as const, title: a.name, on: a.id === user?.id,
          subtitle: a.id === user?.id ? t('сейчас открыт') : undefined, onPress: () => { if (a.id !== user?.id) switchAccount(a.id); } })),
        ...(canAddAccount ? [{ icon: 'add-circle-outline' as const, title: t('Добавить аккаунт'), subtitle: t('Войти во второй аккаунт — этот останется на устройстве'),
          onPress: () => router.push('/login') }] : []),
      ]} />
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
