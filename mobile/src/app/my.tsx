import { router, useFocusEffect } from 'expo-router';
import { useCallback } from 'react';
import { Alert, View } from 'react-native';

import { api } from '@/lib/api';
import { openWeb } from '@/lib/links';
import { useApp } from '@/state/app';
import { Card, Chip, Empty, ErrorBox, Icon, Loading, Screen, Section, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type Item = { id: number; title: string; status: string; status_name: string; hidden: boolean; public: boolean; can_edit: boolean; can_hide: boolean };
type Data = { groups: { key: string; title: string; items: Item[] }[]; create: { key: string; title: string; native: boolean; web: string }[] };

/** «Мои публикации»: все разделы вместе — статус проверки, правка, скрыть, удалить, добавить. */
export default function MyPublications() {
  const { c, t } = useApp();
  const { data, loading, error, reload } = useFetch<Data>('/my/');
  useFocusEffect(useCallback(() => { reload(true); }, [reload]));

  const actions = (key: string, it: Item) => {
    const buttons: any[] = [];
    if (it.public) buttons.push({ text: t('Открыть'), onPress: () => router.push(`/pub/${key}/${it.id}`) });
    if (it.can_edit) buttons.push({ text: t('Изменить'), onPress: () => router.push({ pathname: '/publish/[key]', params: { key, id: String(it.id) } }) });
    if (it.can_hide) buttons.push({ text: it.hidden ? t('Показывать снова') : t('Скрыть'), onPress: async () => { await api(`/my/${key}/${it.id}/`, { body: {} }).catch((e) => Alert.alert(e.message)); reload(); } });
    buttons.push({ text: t('Удалить'), style: 'destructive', onPress: () => Alert.alert(t('Удалить «{title}»?', { title: it.title }), t('Это нельзя отменить.'), [
      { text: t('Отмена'), style: 'cancel' },
      { text: t('Удалить'), style: 'destructive', onPress: async () => { await api(`/my/${key}/${it.id}/`, { method: 'DELETE' }).catch((e) => Alert.alert(e.message)); reload(); } }]) });
    buttons.push({ text: t('Отмена'), style: 'cancel' });
    Alert.alert(it.title, it.status_name, buttons);
  };

  const color = (it: Item) => (it.hidden ? c.inkSoft : it.status === 'approved' ? c.ok : it.status === 'rejected' ? c.bad : c.warn);

  return (
    <Screen back title={t('Мои публикации')} onRefresh={reload} refreshing={loading && !!data}>
      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : (
        <>
          <Section title={t('Добавить')}>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              {data.create.map((x) => (
                <Chip key={x.key} icon="add" label={x.title} onPress={() => (x.native ? router.push(`/publish/${x.key}`) : openWeb(x.web))} />
              ))}
            </View>
          </Section>
          {!data.groups.length ? <Empty icon="document-text-outline" title={t('Публикаций пока нет')} text={t('Объявление, вакансия, услуга — добавьте первую.')} /> : null}
          {data.groups.map((g) => (
            <Section key={g.key} title={g.title}>
              {g.items.map((it) => (
                <Card key={it.id} onPress={() => actions(g.key, it)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                  <View style={{ flex: 1, gap: 4 }}>
                    <Txt kind="h3" numberOfLines={2}>{it.title}</Txt>
                    <Txt kind="small" color={color(it)} style={{ fontWeight: '700' }}>● {it.status_name}</Txt>
                  </View>
                  <Icon name="ellipsis-horizontal" color={c.inkSoft} />
                </Card>
              ))}
            </Section>
          ))}
        </>
      )}
    </Screen>
  );
}
