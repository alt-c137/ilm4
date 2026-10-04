import { router } from 'expo-router';
import { useState } from 'react';
import { Alert } from 'react-native';

import { api } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, Field, Screen, Txt } from '@/ui/kit';

/** Удаление аккаунта — отдельным экраном, чтобы не нажать случайно среди настроек. */
export default function AccountDelete() {
  const { t, signOut } = useApp();
  const [confirm, setConfirm] = useState('');
  const [deleting, setDeleting] = useState(false);
  const del = async () => {
    setDeleting(true);
    try {
      await api('/me/', { method: 'DELETE', body: { confirm } });
      await signOut();
      Alert.alert(t('Аккаунт удалён. Да вознаградит вас Аллах благом.'));
      router.replace('/');
    } catch (e: any) {
      Alert.alert(e.message);
    } finally {
      setDeleting(false);
    }
  };
  return (
    <Screen title={t('Удалить аккаунт')} back>
      <Card style={{ gap: 12 }}>
        <Txt kind="muted">{t('Личные данные сотрутся, публикации снимутся, анкета никяха и фото удалятся. Это нельзя отменить.')}</Txt>
        <Field placeholder={t('Напишите слово «удалить»')} value={confirm} onChangeText={setConfirm} autoCapitalize="none" />
        <Button kind="danger" title={t('Удалить аккаунт')} onPress={del} loading={deleting} disabled={confirm.trim().length < 4} />
      </Card>
    </Screen>
  );
}
