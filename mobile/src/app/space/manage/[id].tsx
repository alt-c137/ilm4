import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, ScrollView, Share, Switch, TextInput, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, Chip, Divider, ErrorBox, Icon, Loading, Screen, Section, Sheet, toast, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type Role = { id: number; name: string; color: string; perms: string[] };
type Chan = { id: number; title: string; topic: string; private: boolean; roles: number[] };
type Invite = { id: number; link: string; uses: number; max_uses: number; expires: string };
type Data = {
  title: string; invite: string; space_roles: Role[]; me: { perms: string[] } | null;
  manage: { perm_choices: { key: string; name: string }[]; channels?: Chan[]; invites?: Invite[]; banned?: { id: number; name: string }[];
    logs?: { time: string; actor: string; action: string; text: string }[] } | null;
  new_invite?: string;
};
type Tab = 'roles' | 'channels' | 'invites' | 'bans' | 'log';
const COLORS = ['#22c55e', '#3b82f6', '#a855f7', '#ec4899', '#ef4444', '#f59e0b', '#14b8a6', '#64748b'];

/** «Управление сообществом» — как настройки сервера в Discord: роли и права, каналы, приглашения, удалённые, журнал. */
export default function SpaceManage() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { c, t } = useApp();
  const { data, setData, loading, error, reload } = useFetch<Data>(`/communities/${id}/`);
  const [tab, setTab] = useState<Tab | null>(null);
  const [role, setRole] = useState<(Omit<Role, 'id'> & { id: number | null }) | null>(null);
  const [chan, setChan] = useState<Chan | null>(null);
  const [inv, setInv] = useState(false);

  if (!data) return <Screen back title={t('Управление')}>{loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />}</Screen>;
  const m = data.manage;
  const perms = data.me?.perms ?? [];
  if (!m) return <Screen back title={t('Управление')}><Txt kind="muted">{t('У вас нет прав на управление этим сообществом.')}</Txt></Screen>;

  const act = async (body: Record<string, unknown>) => {
    try {
      const r = await api<Data>(`/communities/${id}/act/`, { body });
      setData(r);
      return r;
    } catch (e) {
      Alert.alert((e as ApiError).message);
      return null;
    }
  };
  const sure = (title: string, run: () => void) => Alert.alert(title, undefined, [{ text: t('Отмена'), style: 'cancel' }, { text: t('Да'), style: 'destructive', onPress: run }]);
  const tabs: { key: Tab; label: string }[] = [
    ...(perms.includes('manage_roles') ? [{ key: 'roles' as const, label: t('Роли') }] : []),
    ...(m.channels ? [{ key: 'channels' as const, label: t('Каналы') }] : []),
    ...(m.invites ? [{ key: 'invites' as const, label: t('Ссылки') }] : []),
    ...(m.banned ? [{ key: 'bans' as const, label: t('Удалённые') }] : []),
    ...(m.logs ? [{ key: 'log' as const, label: t('Журнал') }] : []),
  ];
  const now = tab ?? tabs[0]?.key;
  const input = { backgroundColor: c.card2, borderRadius: 14, padding: 12, fontSize: 16, color: c.ink } as const;
  const toggle = <T,>(list: T[], x: T) => (list.includes(x) ? list.filter((y) => y !== x) : [...list, x]);

  return (
    <Screen back title={data.title} onRefresh={reload} refreshing={loading}>
      {tabs.length > 1 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }} style={{ marginHorizontal: -16 }} contentInset={{ left: 16, right: 16 }}>
          <View style={{ width: 8 }} />
          {tabs.map((x) => <Chip key={x.key} label={x.label} on={now === x.key} onPress={() => setTab(x.key)} />)}
          <View style={{ width: 8 }} />
        </ScrollView>
      ) : null}

      {now === 'roles' ? (
        <Section title={t('Роли')}>
          <Txt kind="small">{t('Роль — это цвет имени, права и доступ к закрытым каналам. Выдаётся участнику долгим нажатием на него.')}</Txt>
          <Card style={{ paddingVertical: 4 }}>
            {data.space_roles.map((r, i) => (
              <View key={r.id}>
                {i ? <Divider /> : null}
                <Pressable onPress={() => setRole(r)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 }}>
                  <View style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: r.color }} />
                  <Txt style={{ flex: 1, fontWeight: '700' }} color={r.color}>{r.name}</Txt>
                  <Txt kind="small">{r.perms.length ? t('прав: {n}', { n: r.perms.length }) : t('без прав')}</Txt>
                  <Icon name="chevron-forward" size={17} color={c.inkSoft} />
                </Pressable>
              </View>
            ))}
            {!data.space_roles.length ? <Txt kind="muted" style={{ paddingVertical: 12 }}>{t('Своих ролей пока нет.')}</Txt> : null}
          </Card>
          <Button small kind="soft" icon="add" title={t('Новая роль')} onPress={() => setRole({ id: null, name: '', color: COLORS[0], perms: [] })} />
        </Section>
      ) : null}

      {now === 'channels' && m.channels ? (
        <Section title={t('Каналы')}>
          <Txt kind="small">{t('Закрытый канал видят только участники с выбранными ролями. Новый канал — в меню сообщества.')}</Txt>
          <Card style={{ paddingVertical: 4 }}>
            {m.channels.map((ch, i) => (
              <View key={ch.id}>
                {i ? <Divider /> : null}
                <Pressable onPress={() => setChan(ch)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 }}>
                  <Icon name={ch.private ? 'lock-closed-outline' : 'chatbox-outline'} size={19} color={c.inkSoft} />
                  <View style={{ flex: 1 }}>
                    <Txt style={{ fontWeight: '700' }} numberOfLines={1}>{ch.title}</Txt>
                    {ch.topic ? <Txt kind="small" numberOfLines={1}>{ch.topic}</Txt> : null}
                  </View>
                  <Icon name="chevron-forward" size={17} color={c.inkSoft} />
                </Pressable>
              </View>
            ))}
          </Card>
        </Section>
      ) : null}

      {now === 'invites' && m.invites ? (
        <Section title={t('Приглашения')}>
          <Card style={{ gap: 10 }}>
            <Txt kind="label">{t('Постоянная ссылка')}</Txt>
            <Txt selectable numberOfLines={1}>{data.invite}</Txt>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Button small icon="share-outline" title={t('Поделиться')} style={{ flex: 1 }} onPress={() => Share.share({ message: data.invite })} />
              <Button small kind="soft" title={t('Новая ссылка')} style={{ flex: 1 }} onPress={() => sure(t('Старая ссылка перестанет работать. Сменить?'), () => act({ action: 'invite' }))} />
            </View>
          </Card>
          {m.invites.length ? (
            <Card style={{ paddingVertical: 4 }}>
              {m.invites.map((x, i) => (
                <View key={x.id}>
                  {i ? <Divider /> : null}
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 }}>
                    <Pressable style={{ flex: 1 }} onPress={() => Share.share({ message: x.link })}>
                      <Txt numberOfLines={1} style={{ fontWeight: '600' }}>{x.link.replace(/^https?:\/\//, '')}</Txt>
                      <Txt kind="small">{x.expires ? `${t('до')} ${new Date(x.expires).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}` : t('без срока')}
                        {' · '}{x.uses}{x.max_uses ? `/${x.max_uses}` : ''}</Txt>
                    </Pressable>
                    <Pressable hitSlop={8} onPress={() => act({ action: 'invite_delete', invite: x.id })}><Icon name="trash-outline" size={20} color={c.bad} /></Pressable>
                  </View>
                </View>
              ))}
            </Card>
          ) : null}
          <Button small kind="soft" icon="time-outline" title={t('Приглашение со сроком')} onPress={() => setInv(true)} />
        </Section>
      ) : null}

      {now === 'bans' && m.banned ? (
        <Section title={t('Удалённые участники')}>
          {m.banned.length ? (
            <Card style={{ paddingVertical: 4 }}>
              {m.banned.map((b, i) => (
                <View key={b.id}>
                  {i ? <Divider /> : null}
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9 }}>
                    <Txt style={{ flex: 1, fontWeight: '600' }}>{b.name}</Txt>
                    <Button small kind="soft" title={t('Вернуть')} onPress={() => act({ action: 'unban', user: b.id })} />
                  </View>
                </View>
              ))}
            </Card>
          ) : <Txt kind="muted">{t('Никого не удаляли.')}</Txt>}
        </Section>
      ) : null}

      {now === 'log' && m.logs ? (
        <Section title={t('Журнал действий')}>
          {m.logs.length ? (
            <Card style={{ gap: 9 }}>
              {m.logs.map((l, i) => (
                <View key={i} style={{ flexDirection: 'row', gap: 10 }}>
                  <Txt kind="small" style={{ width: 78 }}>{l.time}</Txt>
                  <Txt style={{ flex: 1, fontSize: 14 }}><Txt style={{ fontWeight: '700', fontSize: 14 }}>{l.actor || '—'}</Txt> {l.action} {l.text}</Txt>
                </View>
              ))}
            </Card>
          ) : <Txt kind="muted">{t('Пока пусто.')}</Txt>}
        </Section>
      ) : null}

      {/* роль: имя, цвет, права */}
      <Sheet open={!!role} onClose={() => setRole(null)} title={role?.id ? t('Роль') : t('Новая роль')} items={[]} header={role ? (
        <View style={{ paddingHorizontal: 20, gap: 12, paddingBottom: 10 }}>
          <TextInput value={role.name} onChangeText={(v) => setRole({ ...role, name: v })} maxLength={32} placeholder={t('например: Учитель')} placeholderTextColor={c.inkSoft} style={input} />
          <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
            {COLORS.map((x) => (
              <Pressable key={x} onPress={() => setRole({ ...role, color: x })} style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: x, alignItems: 'center', justifyContent: 'center' }}>
                {role.color === x ? <Icon name="checkmark" size={19} color="#fff" /> : null}
              </Pressable>
            ))}
          </View>
          {m.perm_choices.map((p) => (
            <View key={p.key} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Txt style={{ flex: 1 }}>{p.name}</Txt>
              <Switch value={role.perms.includes(p.key)} onValueChange={() => setRole({ ...role, perms: toggle(role.perms, p.key) })} trackColor={{ true: c.accent, false: c.line }} />
            </View>
          ))}
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button title={t('Сохранить')} style={{ flex: 1 }} disabled={role.name.trim().length < 1}
              onPress={async () => { const r = role; setRole(null); await act({ action: 'role_save', role_id: r.id, name: r.name.trim(), color: r.color, perms: r.perms, hoist: true }); }} />
            {role.id ? <Button kind="soft" title={t('Удалить')} onPress={() => { const r = role; setRole(null); sure(t('Удалить роль?'), () => act({ action: 'role_delete', role_id: r.id })); }} /> : null}
          </View>
        </View>
      ) : null} />

      {/* канал: название, тема, закрытый и для каких ролей */}
      <Sheet open={!!chan} onClose={() => setChan(null)} title={t('Канал')} items={[]} header={chan ? (
        <View style={{ paddingHorizontal: 20, gap: 12, paddingBottom: 10 }}>
          <TextInput value={chan.title} onChangeText={(v) => setChan({ ...chan, title: v })} maxLength={60} placeholder={t('Название канала')} placeholderTextColor={c.inkSoft} style={input} />
          <TextInput value={chan.topic} onChangeText={(v) => setChan({ ...chan, topic: v })} maxLength={200} placeholder={t('тема канала (необязательно)')} placeholderTextColor={c.inkSoft} style={input} />
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <View style={{ flex: 1 }}><Txt style={{ fontWeight: '600' }}>{t('Закрытый канал')}</Txt><Txt kind="small">{t('Видят только выбранные роли')}</Txt></View>
            <Switch value={chan.private} onValueChange={(v) => setChan({ ...chan, private: v })} trackColor={{ true: c.accent, false: c.line }} />
          </View>
          {chan.private ? (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              {data.space_roles.map((r) => {
                const on = chan.roles.includes(r.id);
                return (
                  <Pressable key={r.id} onPress={() => setChan({ ...chan, roles: toggle(chan.roles, r.id) })}
                    style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, borderWidth: 1.5, borderColor: on ? r.color : c.line, backgroundColor: on ? `${r.color}22` : 'transparent' }}>
                    <Txt style={{ fontWeight: '700', fontSize: 14 }} color={on ? r.color : c.inkSoft}>{r.name}</Txt>
                  </Pressable>
                );
              })}
              {!data.space_roles.length ? <Txt kind="small">{t('Сначала создайте роль — вкладка «Роли».')}</Txt> : null}
            </View>
          ) : null}
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button title={t('Сохранить')} style={{ flex: 1 }} disabled={chan.title.trim().length < 1}
              onPress={async () => { const x = chan; setChan(null); await act({ action: 'channel_set', thread: x.id, title: x.title.trim(), topic: x.topic, private: x.private, roles: x.roles }); }} />
            <Button kind="soft" title={t('Удалить')} onPress={() => { const x = chan; setChan(null); sure(t('Удалить канал вместе с перепиской?'), () => act({ action: 'drop_channel', thread: x.id })); }} />
          </View>
        </View>
      ) : null} />

      <Sheet open={inv} onClose={() => setInv(false)} title={t('Приглашение со сроком')} items={[
        { hours: 1, max: 1, title: t('1 час · 1 человек') }, { hours: 24, max: 0, title: t('1 день · без ограничения') },
        { hours: 24, max: 10, title: t('1 день · 10 человек') }, { hours: 168, max: 0, title: t('7 дней · без ограничения') },
      ].map((x) => ({ icon: 'time-outline' as const, title: x.title, onPress: async () => {
        const r = await act({ action: 'invite_new', hours: x.hours, max_uses: x.max });
        if (r?.new_invite) { toast(t('Ссылка создана')); Share.share({ message: r.new_invite }); }
      } }))} />
    </Screen>
  );
}
