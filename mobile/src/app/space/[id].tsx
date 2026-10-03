import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Pressable, Share, TextInput, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { openSiteUrl } from '@/lib/links';
import { useApp } from '@/state/app';
import { Avatar, Badge, Button, Card, ErrorBox, Icon, Loading, Screen, Section, Sheet, Txt, type IconName, type SheetItem } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

import type { SpaceCard } from './index';

type Channel = { id: number; title: string; kind: 'text' | 'news' | 'voice'; unread: number; private?: boolean; people?: { name: string }[] };
type Role = { id: number; name: string; color: string };
type Person = { id: number; name: string; real: string; avatar: string; role: string; role_name: string; roles: Role[]; timeout: boolean };
type Space = SpaceCard & { groups: { id: number; title: string; channels: Channel[] }[]; unread: number; invite: string; people: Person[];
  me: { role: string; nick: string; admin: boolean; mod: boolean; perms: string[] } | null; roles: { key: string; name: string }[];
  space_roles: Role[]; web: string };
const CH_ICON: Record<Channel['kind'], IconName> = { text: 'chatbox-outline', news: 'megaphone-outline', voice: 'volume-medium-outline' };

/** Сообщество: каналы по категориям (каждый — обычный чат), свой ник, участники и роли, управление для админов. */
export default function SpaceScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { c, t, user } = useApp();
  const { data, setData, loading, error, reload } = useFetch<Space>(`/communities/${id}/`);
  useFocusEffect(useCallback(() => { reload(true); }, [reload]));
  const [menu, setMenu] = useState(false);
  const [man, setMan] = useState<Person | null>(null);
  const [ask, setAsk] = useState<{ title: string; hint: string; value: string; body: (v: string) => Record<string, unknown> } | null>(null);
  const [kindFor, setKindFor] = useState<string | null>(null);        // название нового канала ждёт выбора вида

  if (!data) return <Screen back title={t('Сообщество')}>{loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />}</Screen>;
  const act = async (body: Record<string, unknown>) => {
    try {
      const r = await api<Space & { gone?: boolean }>(`/communities/${id}/act/`, { body });
      if (r.gone) router.back(); else setData(r);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const me = data.me;
  const sure = (title: string, body: Record<string, unknown>) => Alert.alert(title, undefined, [
    { text: t('Отмена'), style: 'cancel' }, { text: t('Да'), style: 'destructive', onPress: () => act(body) }]);
  const can = (perm: string) => !!me?.perms.includes(perm);
  const manageable = (p: Person) => p.role !== 'owner' && p.id !== user?.id && (me?.admin || can('kick') || can('timeout') || can('manage_roles'));
  const manItems: SheetItem[] = man && manageable(man) ? [
    ...(me?.admin ? data.roles.filter((r) => r.key !== man.role).map((r) => ({ icon: 'shield-checkmark-outline' as const, title: `${t('Сделать:')} ${r.name}`, onPress: () => act({ action: 'role', user: man.id, role: r.key }) })) : []),
    ...(can('manage_roles') ? data.space_roles.map((r) => {
      const has = man.roles.some((x) => x.id === r.id);
      return { icon: 'pricetag-outline' as const, title: r.name, on: has,
        onPress: () => act({ action: 'member_roles', user: man.id, roles: has ? man.roles.filter((x) => x.id !== r.id).map((x) => x.id) : [...man.roles.map((x) => x.id), r.id] }) };
    }) : []),
    ...(can('timeout') ? [man.timeout
      ? { icon: 'time-outline' as const, title: t('Снять тайм-аут'), onPress: () => act({ action: 'timeout', user: man.id, for: '' }) }
      : { icon: 'time-outline' as const, title: t('Тайм-аут: 1 час'), subtitle: t('Не сможет писать в каналах'), onPress: () => act({ action: 'timeout', user: man.id, for: '1h' }) }] : []),
    ...(can('kick') ? [{ icon: 'ban-outline' as const, danger: true, title: t('Удалить из сообщества'), onPress: () => sure(t('Удалить участника из сообщества?'), { action: 'kick', user: man.id }) }] : []),
  ] : [];

  return (
    <Screen back title={data.title} onRefresh={reload} refreshing={loading}
      right={me ? <Pressable onPress={() => setMenu(true)} hitSlop={10}><Icon name="ellipsis-vertical" size={21} /></Pressable> : undefined}>
      <View style={{ alignItems: 'center', gap: 6 }}>
        <Avatar uri={data.icon} name={data.title} size={88} hue={data.id} />
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
          <Txt kind="h2" style={{ textAlign: 'center' }}>{data.title}</Txt>
          {data.verified ? <Icon name="checkmark-circle" size={18} color={c.accent} /> : null}
        </View>
        <Txt kind="small">{t('участников: {n}', { n: data.members })}{data.public ? '' : ` · ${t('закрытое')}`}</Txt>
        {data.about ? <Txt kind="muted" style={{ textAlign: 'center' }}>{data.about}</Txt> : null}
      </View>
      {!me ? <Button title={t('Вступить')} onPress={() => act({ action: 'join' })} /> : null}

      <Section title={t('Каналы')}>
        <Card style={{ paddingVertical: 6 }}>
          {data.groups.map((g) => (
            <View key={g.id}>
              {g.title ? <Txt kind="label" style={{ marginTop: 8, marginBottom: 2 }}>{g.title}</Txt> : null}
              {g.channels.map((ch) => (
                <Pressable key={`${ch.kind}${ch.id}`} disabled={!me}
                  onPress={() => (ch.kind === 'voice' ? openSiteUrl(`${data.web}voice/${ch.id}/`) : router.push(`/chat/${ch.id}`))}
                  onLongPress={can('manage_channels') ? () => sure(t('Удалить канал вместе с перепиской?'), { action: 'drop_channel', [ch.kind === 'voice' ? 'voice' : 'thread']: ch.id }) : undefined}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 }}>
                  <Icon name={ch.private ? 'lock-closed-outline' : CH_ICON[ch.kind]} size={19} color={ch.unread ? c.ink : c.inkSoft} />
                  <Txt style={{ flex: 1, fontWeight: ch.unread ? '800' : '600' }} color={ch.unread ? c.ink : c.inkSoft} numberOfLines={1}>{ch.title}</Txt>
                  {ch.kind === 'voice' ? <Txt kind="small" style={{ fontSize: 11.5 }}>{ch.people?.length ? t('в комнате: {n}', { n: ch.people.length }) : t('войти')}</Txt> : ch.unread ? <Badge n={ch.unread} /> : null}
                </Pressable>
              ))}
            </View>
          ))}
        </Card>
      </Section>

      {me ? (
        <>
          <Section title={t('Я в этом сообществе')}>
            <Card onPress={() => setAsk({ title: t('Мой ник здесь'), hint: t('Так вас видят в каналах этого сообщества. Пусто — обычное имя.'), value: me.nick, body: (v) => ({ action: 'nick', nick: v }) })}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Icon name="at" size={20} color={c.accent} />
              <View style={{ flex: 1 }}><Txt style={{ fontWeight: '700' }}>{me.nick || user?.name}</Txt><Txt kind="small">{t('Мой ник здесь')}</Txt></View>
              <Icon name="create-outline" size={18} color={c.inkSoft} />
            </Card>
          </Section>
          <Section title={t('Участники')}>
            <Card style={{ paddingVertical: 4 }}>
              {data.people.map((p, i) => (
                <Pressable key={p.id} onPress={() => router.push(`/user/${p.id}`)} onLongPress={() => setMan(p)} delayLongPress={350}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 9, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
                  <Avatar uri={p.avatar} name={p.name} size={40} hue={p.id} />
                  <View style={{ flex: 1 }}>
                    <Txt style={{ fontWeight: '700' }} color={p.roles[0]?.color} numberOfLines={1}>{p.name}</Txt>
                    <Txt kind="small" numberOfLines={1}>{[p.role_name, ...p.roles.map((r) => r.name), p.timeout ? t('тайм-аут') : '', p.real].filter(Boolean).join(' · ')}</Txt>
                  </View>
                  {manageable(p) ? <Pressable onPress={() => setMan(p)} hitSlop={10}><Icon name="ellipsis-horizontal" size={19} color={c.inkSoft} /></Pressable> : null}
                </Pressable>
              ))}
            </Card>
          </Section>
        </>
      ) : null}

      <Sheet open={menu} onClose={() => setMenu(false)} items={[
        { icon: 'albums-outline' as const, title: t('Доска задач'), onPress: () => router.push(`/space/board/${id}`) },
        ...(can('manage_channels') ? [
          { icon: 'add' as const, title: t('Новый канал'), onPress: () => setTimeout(() => setAsk({ title: t('Новый канал'), hint: t('Название канала'), value: '', body: (v) => { setKindFor(v); return {}; } }), 300) },
          { icon: 'folder-open-outline' as const, title: t('Новая категория'), onPress: () => setTimeout(() => setAsk({ title: t('Новая категория'), hint: t('например: Учёба'), value: '', body: (v) => ({ action: 'category', title: v }) }), 300) },
        ] : []),
        ...(can('manage_roles') ? [
          { icon: 'pricetag-outline' as const, title: t('Новая роль'), onPress: () => setTimeout(() => setAsk({ title: t('Новая роль'), hint: t('Цвет, права и закрытые каналы настраиваются на сайте — «Управление сообществом».'), value: '', body: (v) => ({ action: 'role_save', name: v }) }), 300) },
        ] : []),
        ...(can('manage_space') ? [
          { icon: 'link-outline' as const, title: t('Ссылка-приглашение'), onPress: () => { Share.share({ message: data.invite }); } },
          { icon: 'create-outline' as const, title: t('Изменить название'), onPress: () => setTimeout(() => setAsk({ title: t('Название'), hint: '', value: data.title, body: (v) => ({ action: 'update', title: v }) }), 300) },
          { icon: (data.public ? 'lock-closed-outline' : 'earth-outline') as IconName, title: data.public ? t('Сделать закрытым') : t('Сделать открытым'), onPress: () => act({ action: 'update', is_public: !data.public }) },
          { icon: 'settings-outline' as const, title: t('Управление сообществом'), subtitle: t('Роли, права, закрытые каналы, приглашения со сроком, журнал'), onPress: () => openSiteUrl(data.web) },
        ] : []),
        { icon: 'exit-outline', danger: true, title: t('Выйти из сообщества'), onPress: () => sure(t('Выйти из сообщества?'), { action: 'leave' }) },
        ...(me?.role === 'owner' ? [{ icon: 'trash-outline' as const, danger: true, title: t('Удалить сообщество'),
          onPress: () => sure(t('Удалить сообщество со всеми каналами и перепиской? Это нельзя отменить.'), { action: 'delete' }) }] : []),
      ]} />
      <Sheet open={!!man && manItems.length > 0} onClose={() => setMan(null)} title={man?.name} items={manItems.map((x) => ({ ...x, onPress: () => { x.onPress(); setMan(null); } }))} />
      <Sheet open={kindFor !== null} onClose={() => setKindFor(null)} title={t('Вид канала')} items={[
        { icon: 'chatbox-outline', title: t('Текстовый — пишут все'), onPress: () => act({ action: 'channel', title: kindFor, kind: 'text' }) },
        { icon: 'megaphone-outline', title: t('Объявления — пишут админы'), onPress: () => act({ action: 'channel', title: kindFor, kind: 'news' }) },
        { icon: 'volume-medium-outline', title: t('Голосовая комната'), onPress: () => act({ action: 'channel', title: kindFor, kind: 'voice' }) },
      ]} />
      <Sheet open={!!ask} onClose={() => setAsk(null)} title={ask?.title} items={[]} header={ask ? (
        <View style={{ paddingHorizontal: 20, gap: 10, paddingBottom: 10 }}>
          {ask.hint ? <Txt kind="small">{ask.hint}</Txt> : null}
          <TextInput value={ask.value} onChangeText={(v) => setAsk({ ...ask, value: v })} autoFocus maxLength={80} placeholderTextColor={c.inkSoft}
            style={{ backgroundColor: c.card2, borderRadius: 14, padding: 12, fontSize: 16, color: c.ink }} />
          <Button title={t('Сохранить')} onPress={() => { const body = ask.body(ask.value.trim()); setAsk(null); if (body.action) act(body); }} />
        </View>
      ) : null} />
    </Screen>
  );
}
