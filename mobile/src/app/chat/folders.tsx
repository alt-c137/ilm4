import { router, useFocusEffect } from 'expo-router';
import { useCallback } from 'react';
import { Alert, Pressable, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, Icon, Screen, Section, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

export type Folder = { id: number; title: string; emoji: string; types: string[]; no_muted: boolean; no_read: boolean; no_archived: boolean;
  include: number[]; exclude: number[] };
type Data = { items: Folder[]; recommended: { key: string; title: string; emoji: string; hint: string }[]; types: { key: string; name: string }[]; max: number };

/** «Папки с чатами» — как в настройках Telegram: свои папки, их порядок, готовые папки одним нажатием. */
export default function Folders() {
  const { c, t } = useApp();
  const { data, setData, reload } = useFetch<Data>('/chat/folders/');
  useFocusEffect(useCallback(() => { reload(true); }, [reload]));
  const post = async (body: Record<string, unknown>) => {
    try {
      setData(await api<Data>('/chat/folders/', { body }));
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const move = (i: number, by: number) => {
    const ids = (data?.items ?? []).map((f) => f.id);
    const j = i + by;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    post({ order: ids });
  };
  const remove = (f: Folder) => Alert.alert(t('Удалить папку?'), t('Сами чаты останутся.'), [
    { text: t('Отмена'), style: 'cancel' },
    { text: t('Удалить'), style: 'destructive', onPress: async () => {
      try {
        await api(`/chat/folders/${f.id}/`, { method: 'DELETE' });
        reload(true);
      } catch (e) {
        Alert.alert((e as ApiError).message);
      }
    } },
  ]);
  const round = { width: 34, height: 34, borderRadius: 17, alignItems: 'center' as const, justifyContent: 'center' as const, backgroundColor: c.card2 };
  const items = data?.items ?? [];
  const full = !!data && items.length >= data.max;

  return (
    <Screen title={t('Папки с чатами')} back>
      <Txt kind="muted">{t('Разложите чаты по своим папкам: вкладки появятся над списком чатов. Название, состав и порядок — как вам удобно.')}</Txt>
      <Section title={t('Мои папки')}>
        <Card style={{ paddingVertical: 4 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10 }}>
            <View style={{ width: 36, height: 36, borderRadius: 11, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}><Icon name="chatbubbles" size={18} color={c.accentD} /></View>
            <View style={{ flex: 1 }}>
              <Txt style={{ fontWeight: '700' }}>{t('Все')}</Txt>
              <Txt kind="small">{t('Все чаты, кроме архива. Эта вкладка есть всегда')}</Txt>
            </View>
          </View>
          {items.map((f, i) => (
            <View key={f.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9, borderTopWidth: 0.5, borderTopColor: c.line }}>
              <Pressable onPress={() => router.push(`/chat/folder/${f.id}`)} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={{ width: 36, height: 36, borderRadius: 11, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name="folder" size={18} color={c.accentD} />
                </View>
                <View style={{ flex: 1 }}>
                  <Txt style={{ fontWeight: '700' }} numberOfLines={1}>{f.title}</Txt>
                  <Txt kind="small" numberOfLines={1}>{t('Изменить состав и название')}</Txt>
                </View>
              </Pressable>
              <Pressable onPress={() => move(i, -1)} disabled={i === 0} style={[round, { opacity: i === 0 ? 0.35 : 1 }]} accessibilityLabel={t('Выше')}><Icon name="chevron-up" size={18} /></Pressable>
              <Pressable onPress={() => move(i, 1)} disabled={i === items.length - 1} style={[round, { opacity: i === items.length - 1 ? 0.35 : 1 }]} accessibilityLabel={t('Ниже')}><Icon name="chevron-down" size={18} /></Pressable>
              <Pressable onPress={() => remove(f)} style={[round, { backgroundColor: 'transparent' }]} accessibilityLabel={t('Удалить')}><Icon name="trash-outline" size={18} color={c.bad} /></Pressable>
            </View>
          ))}
        </Card>
        {!full ? <Button kind="soft" icon="add" title={t('Создать папку')} onPress={() => router.push('/chat/folder/new')} />
          : <Txt kind="small">{t('Можно создать не больше {n} папок.', { n: data?.max ?? 10 })}</Txt>}
      </Section>
      {data?.recommended.length && !full ? (
        <Section title={t('Готовые папки')}>
          <Card style={{ paddingVertical: 4 }}>
            {data.recommended.map((r, i) => (
              <View key={r.key} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
                <View style={{ width: 36, height: 36, borderRadius: 11, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}><Icon name="folder-open-outline" size={18} color={c.accentD} /></View>
                <View style={{ flex: 1 }}>
                  <Txt style={{ fontWeight: '700' }}>{r.title}</Txt>
                  <Txt kind="small" numberOfLines={2}>{r.hint}</Txt>
                </View>
                <Button small title={t('Добавить')} onPress={() => post({ recommended: r.key })} />
              </View>
            ))}
          </Card>
        </Section>
      ) : null}
      <Txt kind="small">{t('Подсказка: долгое нажатие на чат — закрепить, убрать в архив, добавить в папку. Долгое нажатие на вкладку — изменить папку.')}</Txt>
    </Screen>
  );
}
