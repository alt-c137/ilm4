import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, TextInput, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, ErrorBox, Icon, Loading, Screen, Section, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type Task = { id: number; title: string; note: string; assignee: string; due: string; mine: boolean };
type Board = { title: string; columns: { key: 'todo' | 'doing' | 'done'; title: string; tasks: Task[] }[] };
const NEXT = { todo: 'doing', doing: 'done', done: 'done' } as const;
const PREV = { todo: 'todo', doing: 'todo', done: 'doing' } as const;

/** Доска задач сообщества (канбан): идеи → делаем → готово. Взять задачу в работу может любой участник. */
export default function SpaceBoard() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { c, t } = useApp();
  const { data, setData, loading, error, reload } = useFetch<Board>(`/communities/${id}/board/`);
  const [title, setTitle] = useState('');
  const post = async (body: Record<string, unknown>) => {
    try {
      setData(await api<Board>(`/communities/${id}/board/`, { body }));
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  if (!data) return <Screen back title={t('Доска задач')}>{loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />}</Screen>;
  const tint = { todo: c.inkSoft, doing: '#d97706', done: '#16a34a' };
  return (
    <Screen back title={t('Доска задач')} onRefresh={reload} refreshing={loading}>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <TextInput value={title} onChangeText={setTitle} placeholder={t('Новая идея или задача')} placeholderTextColor={c.inkSoft} maxLength={160}
          style={{ flex: 1, backgroundColor: c.card, borderRadius: 14, paddingHorizontal: 14, height: 46, fontSize: 16, color: c.ink }} />
        <Button title={t('Добавить')} small disabled={title.trim().length < 2} onPress={() => { post({ action: 'save', title }); setTitle(''); }} />
      </View>
      {data.columns.map((col) => (
        <Section key={col.key} title={`${col.title} · ${col.tasks.length}`}>
          {col.tasks.length ? col.tasks.map((x) => (
            <Card key={x.id} style={{ gap: 6, borderLeftWidth: 4, borderLeftColor: tint[col.key] }}>
              <Txt style={{ fontWeight: '700' }}>{x.title}</Txt>
              {x.note ? <Txt kind="small">{x.note}</Txt> : null}
              {x.assignee || x.due ? <Txt kind="small">{[x.assignee, x.due ? x.due.slice(8, 10) + '.' + x.due.slice(5, 7) : ''].filter(Boolean).join(' · ')}</Txt> : null}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                {col.key !== 'todo' ? <Pressable onPress={() => post({ action: 'move', task: x.id, status: PREV[col.key] })} hitSlop={8}><Icon name="arrow-back-circle-outline" size={24} color={c.inkSoft} /></Pressable> : null}
                {x.mine ? <Pressable onPress={() => Alert.alert(t('Удалить задачу?'), undefined, [{ text: t('Отмена'), style: 'cancel' }, { text: t('Удалить'), style: 'destructive', onPress: () => post({ action: 'delete', task: x.id }) }])} hitSlop={8}><Icon name="trash-outline" size={20} color={c.inkSoft} /></Pressable> : null}
                <View style={{ flex: 1 }} />
                {col.key !== 'done' ? <Button small kind="soft" title={col.key === 'todo' ? t('Взять в работу') : t('Готово')} onPress={() => post({ action: 'move', task: x.id, status: NEXT[col.key] })} /> : null}
              </View>
            </Card>
          )) : <Txt kind="small" style={{ paddingHorizontal: 4 }}>{t('Пусто')}</Txt>}
        </Section>
      ))}
    </Screen>
  );
}
