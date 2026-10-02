import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Empty, ErrorBox, Loading, Screen } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

/** Ссылка-приглашение в общий трекер (ilm4.com/tracker/join/код/). */
export default function BoardJoin() {
  const { code } = useLocalSearchParams<{ code: string }>();
  const { t } = useApp();
  const { data, loading, error, reload } = useFetch<{ id: number; title: string; emoji: string; members: number; member: boolean; owner_name: string }>(`/tracker/join/${code}/`);
  const [busy, setBusy] = useState(false);
  const join = async () => {
    setBusy(true);
    try {
      const r = await api<{ id: number }>(`/tracker/join/${code}/`, { body: {} });
      router.replace(`/habits/board/${r.id}`);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen back title={t('Общий трекер')}>
      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : (
        <Empty icon="people-outline" title={`${data.emoji} ${data.title}`}
          text={t('{name} зовёт вас вести трекер вместе. Участники видят отметки друг друга.', { name: data.owner_name })}
          action={data.member ? <Button title={t('Открыть')} onPress={() => router.replace(`/habits/board/${data.id}`)} />
            : <Button title={t('Присоединиться')} onPress={join} loading={busy} />} />
      )}
    </Screen>
  );
}
