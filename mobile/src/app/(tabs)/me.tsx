import { router } from 'expo-router';
import { Alert, Pressable, View } from 'react-native';

import { openWeb } from '@/lib/links';
import { useApp } from '@/state/app';
import { Avatar, Button, Card, Divider, Icon, Row, Screen, Txt } from '@/ui/kit';

export default function Me() {
  const { c, t, user, signOut, moduleOn, refreshMe } = useApp();
  return (
    <Screen title={t('Профиль')} onRefresh={user ? refreshMe : undefined}>
      {user ? (
        <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }} onPress={() => router.push('/profile-edit')}>
          <Avatar uri={user.avatar} name={user.name} size={60} hue={user.id} />
          <View style={{ flex: 1 }}>
            <Txt kind="h2" numberOfLines={1}>{user.name}{user.verified ? ' ✓' : ''}</Txt>
            <Txt kind="small" numberOfLines={1}>{user.email || (user.telegram ? 'Telegram' : '')}</Txt>
          </View>
          <Icon name="create-outline" color={c.accent} />
        </Card>
      ) : (
        <Card style={{ gap: 12, alignItems: 'center' }}>
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

      <Card style={{ paddingVertical: 4 }}>
        {user && moduleOn('nikah') ? <><Row icon="heart-outline" title={t('Никях')} subtitle={user.nikah ? t('Моя анкета, симпатии, пары') : t('Создать анкету')} onPress={() => router.push('/nikah')} /><Divider /></> : null}
        {user ? <><Row icon="notifications-outline" title={t('Уведомления')} onPress={() => router.push('/notifications')} /><Divider /></> : null}
        {user ? <><Row icon="document-text-outline" title={t('Мои публикации')} subtitle={t('Объявления, вакансии, услуги')} onPress={() => router.push('/my')} /><Divider /></> : null}
        <Row icon="moon-outline" title={t('Намаз и азан')} onPress={() => router.push('/prayer-settings')} />
        <Divider />
        <Row icon="settings-outline" title={t('Настройки')} subtitle={t('Язык, тема, аккаунт')} onPress={() => router.push('/settings')} />
      </Card>

      <Card style={{ paddingVertical: 4 }}>
        <Row icon="heart-circle-outline" title={t('Поддержать проект')} onPress={() => openWeb('/support/', false)} />
        <Divider />
        <Row icon="shield-checkmark-outline" title={t('Правила')} onPress={() => openWeb('/rules/', false)} />
        <Divider />
        <Row icon="lock-closed-outline" title={t('Политика конфиденциальности')} onPress={() => openWeb('/privacy/', false)} />
        <Divider />
        <Row icon="star-outline" title={t('Как принять ислам')} onPress={() => openWeb('/islam/', false)} />
      </Card>

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
