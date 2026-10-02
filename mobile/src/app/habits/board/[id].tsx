import * as Clipboard from 'expo-clipboard';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Pressable, Share, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Button, Card, Empty, ErrorBox, Icon, Loading, Screen, Section, Segmented, Sheet, Txt, type SheetItem } from '@/ui/kit';
import { HabitRow, isoDay, type Habit } from '@/ui/tracker';
import { useFetch } from '@/ui/useFetch';

type Man = { id: number; name: string; avatar: string; points: number; total: number; rate: number; me: boolean; owner: boolean; place?: number };
type Board = { id: number; title: string; emoji: string; compete: boolean; members: number; owner: boolean; day: string; today: string;
  items: Habit[]; people: Man[]; period: number; invite_link: string };

/** Общий трекер: привычки с отметками каждого, таблица (если включено соревнование), приглашение. */
export default function BoardScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { c, t } = useApp();
  const [period, setPeriod] = useState<'7' | '30'>('7');
  const day = isoDay();
  const { data, setData, loading, error, reload } = useFetch<Board>(`/tracker/boards/${id}/?day=${day}&days=${period}`);
  const [menu, setMenu] = useState(false);
  useFocusEffect(useCallback(() => { reload(true); }, [reload]));

  if (!data) return <Screen back title="">{loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />}</Screen>;
  const fail = (e: unknown) => Alert.alert((e as ApiError).message);
  const post = async (body: Record<string, unknown>) => {
    try {
      const r = await api<Board & { left?: boolean }>(`/tracker/boards/${id}/`, { body: { ...body, day, days: Number(period) } });
      if (r.left) return router.back();
      setData(r);
    } catch (e) {
      fail(e);
    }
  };
  const mark = async (h: Habit, value?: number) => {
    try {
      await api(`/tracker/habits/${h.id}/log/`, { body: value === undefined ? { day } : { day, value } });
      reload(true);
    } catch (e) {
      fail(e);
    }
  };
  const confirm = (title: string, run: () => void) => Alert.alert(title, undefined, [{ text: t('Отмена'), style: 'cancel' }, { text: t('Да'), style: 'destructive', onPress: run }]);
  const items: SheetItem[] = data.owner ? [
    { icon: 'trophy-outline', title: data.compete ? t('Выключить соревнование') : t('Включить соревнование'), subtitle: t('Таблица: кто сколько выполнил за период'), onPress: () => post({ compete: data.compete ? '' : '1' }) },
    { icon: 'refresh-outline', title: t('Сделать новую ссылку'), subtitle: t('Старая перестанет работать'), onPress: () => confirm(t('Старая ссылка перестанет работать. Продолжить?'), () => post({ new_link: 1 })) },
    { icon: 'trash-outline', danger: true, title: t('Удалить трекер'), subtitle: t('У всех участников, вместе с отметками'),
      onPress: () => confirm(t('Удалить трекер у всех участников?'), async () => { try { await api(`/tracker/boards/${id}/`, { method: 'DELETE' }); router.back(); } catch (e) { fail(e); } }) },
  ] : [
    { icon: 'exit-outline', danger: true, title: t('Выйти из трекера'), subtitle: t('Ваши отметки здесь удалятся'), onPress: () => confirm(t('Выйти из трекера?'), () => post({ leave: 1 })) },
  ];
  const medal = (n?: number) => (n === 1 ? '🥇' : n === 2 ? '🥈' : n === 3 ? '🥉' : String(n ?? ''));

  return (
    <Screen back title={`${data.emoji} ${data.title}`} onRefresh={reload} refreshing={loading}
      right={
        <View style={{ flexDirection: 'row', gap: 14, alignItems: 'center' }}>
          <Pressable onPress={() => router.push({ pathname: '/habits/edit', params: { board: String(id) } })} hitSlop={8} accessibilityLabel={t('Добавить привычку')}><Icon name="add-circle" size={27} color={c.accent} /></Pressable>
          <Pressable onPress={() => setMenu(true)} hitSlop={8} accessibilityLabel={t('Ещё')}><Icon name="ellipsis-vertical" size={21} /></Pressable>
        </View>}>
      {data.items.length ? (
        <View style={{ gap: 8 }}>
          {data.items.map((h) => <HabitRow key={h.id} h={h} hideBoard canMark onToggle={(x) => mark(x)} onStep={(x, by) => mark(x, Math.max(0, x.value + by))}
            onEdit={(x) => router.push({ pathname: '/habits/edit', params: { id: String(x.id) } })} />)}
        </View>
      ) : (
        <Empty icon="people-outline" title={t('Пока пусто')} text={t('Добавьте первую общую привычку — её увидят все участники, а отмечать каждый будет сам.')}
          action={<Button small icon="add" title={t('Добавить привычку')} onPress={() => router.push({ pathname: '/habits/edit', params: { board: String(id) } })} />} />
      )}

      <Section title={data.compete ? `🏆 ${t('Таблица')}` : t('Участники')}>
        <Segmented value={period} onChange={setPeriod} options={[{ key: '7', label: t('{n} дней', { n: 7 }) }, { key: '30', label: t('{n} дней', { n: 30 }) }]} />
        <View style={{ backgroundColor: c.card, borderRadius: 20, overflow: 'hidden' }}>
          {data.people.map((p, i) => (
            <Pressable key={p.id} onPress={() => router.push(`/user/${p.id}`)}
              onLongPress={data.owner && !p.me ? () => confirm(t('Убрать из трекера?'), () => post({ remove: p.id })) : undefined}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, paddingHorizontal: 14, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line, backgroundColor: p.me ? c.accentSoft : 'transparent' }}>
              {data.compete ? <Txt style={{ width: 26, textAlign: 'center', fontSize: 18, fontWeight: '800' }} color={c.inkSoft}>{medal(p.place)}</Txt> : null}
              <Avatar uri={p.avatar} name={p.name} size={38} hue={p.id} />
              <View style={{ flex: 1, gap: 5 }}>
                <Txt style={{ fontWeight: '700' }} numberOfLines={1}>{p.name}{p.owner ? ` · ${t('владелец')}` : ''}</Txt>
                <View style={{ height: 6, borderRadius: 3, backgroundColor: c.line, overflow: 'hidden' }}><View style={{ width: `${p.rate}%`, height: 6, backgroundColor: c.accent, borderRadius: 3 }} /></View>
              </View>
              <Txt style={{ fontWeight: '800', fontSize: 16 }}>{p.points}<Txt kind="small">/{p.total}</Txt></Txt>
            </Pressable>
          ))}
        </View>
        {data.owner ? <Txt kind="small" style={{ paddingHorizontal: 4 }}>{t('Убрать участника — долгое нажатие на его строку.')}</Txt> : null}
      </Section>

      <Section title={t('Позвать людей')}>
        <Card style={{ gap: 10 }}>
          <Txt selectable style={{ fontWeight: '600' }}>{data.invite_link.replace(/^https?:\/\//, '')}</Txt>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <Button small kind="soft" style={{ flex: 1 }} icon="copy-outline" title={t('Копировать')} onPress={async () => { await Clipboard.setStringAsync(data.invite_link); Alert.alert(t('Скопировано')); }} />
            <Button small kind="soft" style={{ flex: 1 }} icon="share-outline" title={t('Поделиться')} onPress={() => Share.share({ message: `${data.title}\n${data.invite_link}` })} />
          </View>
        </Card>
      </Section>
      <Sheet open={menu} onClose={() => setMenu(false)} title={data.title} items={items} />
    </Screen>
  );
}
