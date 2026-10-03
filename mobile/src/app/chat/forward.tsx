import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, FlatList, Pressable, Switch, TextInput, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Button, Icon, Screen, Skeleton, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type Row = { id: number | 'saved'; title: string; avatar: string; other_id: number | null; room: string; saved?: boolean };

/** «Переслать» — как в Telegram: выбрать один или несколько чатов; первым идёт «Избранное». */
export default function Forward() {
  const { ids } = useLocalSearchParams<{ ids: string }>();
  const { c, t } = useApp();
  const { data, loading } = useFetch<{ items: Row[] }>('/chat/');
  const [picked, setPicked] = useState<(number | 'saved')[]>([]);
  const [hide, setHide] = useState(false);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const needle = q.trim().toLowerCase();
  const rows: Row[] = [{ id: 'saved' as const, title: t('Избранное'), avatar: '', other_id: null, room: '', saved: true },
    ...(data?.items ?? []).filter((x) => !x.saved)].filter((x) => !needle || x.title.toLowerCase().includes(needle));
  const toggle = (id: number | 'saved') => setPicked((old) => (old.includes(id) ? old.filter((x) => x !== id) : old.length < 10 ? [...old, id] : old));
  const send = async () => {
    setBusy(true);
    try {
      await api('/chat/forward/', { body: { ids: (ids ?? '').split(',').filter(Boolean), to: picked, hide } });
      if (picked.length === 1 && picked[0] !== 'saved') router.replace(`/chat/${picked[0]}`);
      else router.back();
    } catch (e) {
      Alert.alert((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen title={t('Переслать')} back scroll={false} padded={false}>
      <FlatList
        data={rows}
        keyExtractor={(x) => String(x.id)}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ paddingHorizontal: 12, paddingBottom: 120 }}
        ListHeaderComponent={
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, height: 42, borderRadius: 21, backgroundColor: c.card, borderWidth: 1, borderColor: c.line, paddingHorizontal: 14, marginBottom: 6 }}>
            <Icon name="search" size={17} color={c.inkSoft} />
            <TextInput value={q} onChangeText={setQ} placeholder={t('Поиск')} placeholderTextColor={c.inkSoft} style={{ flex: 1, fontSize: 16, color: c.ink, paddingVertical: 0 }} />
          </View>}
        ListEmptyComponent={loading ? <Skeleton rows={7} /> : null}
        renderItem={({ item: x }) => {
          const on = picked.includes(x.id);
          return (
            <Pressable onPress={() => toggle(x.id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 8, paddingHorizontal: 6 }}>
              {x.saved ? <View style={{ width: 46, height: 46, borderRadius: 23, backgroundColor: '#5b76f7', alignItems: 'center', justifyContent: 'center' }}><Icon name="bookmark" size={21} color="#fff" /></View>
                : <Avatar uri={x.avatar} name={x.title} size={46} hue={x.other_id ?? Number(x.id)} />}
              <Txt style={{ flex: 1, fontSize: 16, fontWeight: '600' }} numberOfLines={1}>{x.title}</Txt>
              <View style={{ width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: on ? c.accent : c.line, backgroundColor: on ? c.accent : 'transparent', alignItems: 'center', justifyContent: 'center' }}>
                {on ? <Icon name="checkmark" size={15} color="#fff" /> : null}
              </View>
            </Pressable>
          );
        }}
      />
      <View style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: 12, paddingBottom: 22, gap: 8, backgroundColor: c.card, borderTopWidth: 0.5, borderTopColor: c.line }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <Txt style={{ flex: 1 }} kind="small">{t('Скрыть имя автора')}</Txt>
          <Switch value={hide} onValueChange={setHide} trackColor={{ true: c.accent, false: c.line }} />
        </View>
        <Button title={picked.length > 1 ? `${t('Переслать')} · ${picked.length}` : t('Переслать')} icon="arrow-redo" disabled={!picked.length} loading={busy} onPress={send} />
      </View>
    </Screen>
  );
}
