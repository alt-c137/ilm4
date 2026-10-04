import * as Clipboard from 'expo-clipboard';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, ScrollView, RefreshControl, Share, Switch, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Button, Card, ErrorBox, Field, Icon, Loading, OfflineBar, Press, Screen, Section, Sheet, Txt, type SheetItem } from '@/ui/kit';
import { ProfileActions, ProfileHead, type Action } from '@/ui/profile';
import { PhotoViewer } from '@/ui/photo-viewer';
import { useFetch } from '@/ui/useFetch';

type Person = { id: number; name: string; avatar: string; role: 'owner' | 'admin' | 'member'; role_name: string };
type Info = { id: number; kind: 'group' | 'channel'; title: string; about: string; handle: string; avatar: string; members: number;
  verified: boolean; closed: boolean; member: boolean; admin: boolean; role: string; muted: boolean; public: boolean;
  only_admins_post: boolean; invite_link: string; public_link: string; people: Person[];
  protected?: boolean; reactions_on?: boolean; comments_on?: boolean; slow_seconds?: number };
type Edit = { title: string; about: string; is_public: boolean; handle: string; only_admins_post: boolean;
  protected: boolean; reactions_on: boolean; comments_on: boolean; slow_seconds: number };
const SLOW = [0, 10, 30, 60, 300, 900, 3600];

/** Сведения о группе / канале: описание, приглашение, участники, настройки (владелец и админы). */
export default function RoomInfo() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { c, t, user } = useApp();
  const { data, setData, loading, error, reload } = useFetch<Info>(`/chat/${id}/room/`);
  const [edit, setEdit] = useState<Edit | null>(null);
  const [photo, setPhoto] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);
  const [who, setWho] = useState<Person | null>(null);

  if (!data) return <Screen back title="">{loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />}</Screen>;
  const channel = data.kind === 'channel';
  const owner = data.role === 'owner';

  const act = async (action: string, confirm?: string) => {
    const run = async () => {
      setBusy(true);
      try {
        const r = await api(`/chat/${id}/room/${action}/`, { body: {} });
        if (r.left) return router.dismissTo('/chats');
        setData(r);
      } catch (e: any) {
        Alert.alert(e.message);
      } finally {
        setBusy(false);
      }
    };
    if (!confirm) return run();
    Alert.alert(confirm, undefined, [{ text: t('Отмена'), style: 'cancel' }, { text: t('Да'), style: 'destructive', onPress: run }]);
  };
  const memberAct = (p: Person, action: string) => api(`/chat/${id}/member/${p.id}/${action}/`, { body: {} }).then(setData).catch((e) => Alert.alert(e.message));
  const memberMenu = (p: Person): SheetItem[] => [
    { icon: 'person-outline', title: t('Открыть профиль'), onPress: () => router.push(`/user/${p.id}`) },
    ...(owner && p.role !== 'owner' && p.id !== user?.id ? [{ icon: 'star-outline' as const, title: p.role === 'admin' ? t('Снять админа') : t('Сделать админом'), onPress: () => memberAct(p, p.role === 'admin' ? 'unadmin' : 'admin') }] : []),
    ...(data.admin && p.id !== user?.id && p.role !== 'owner' && (owner || p.role === 'member') ? [{ icon: 'person-remove-outline' as const, danger: true, title: t('Удалить из чата'), onPress: () => memberAct(p, 'remove') }] : []),
  ];
  const save = async () => {
    if (!edit) return;
    setBusy(true);
    try {
      const flag = (v: boolean) => (v ? '1' : '');
      setData(await api(`/chat/${id}/room/`, { body: { ...edit, is_public: flag(edit.is_public), only_admins_post: flag(edit.only_admins_post),
        protected: flag(edit.protected), reactions_on: flag(edit.reactions_on), comments_on: flag(edit.comments_on), slow_seconds: String(edit.slow_seconds) } }));
      setEdit(null);
    } catch (e: any) {
      Alert.alert(e.message);
    } finally {
      setBusy(false);
    }
  };
  const link = data.public_link || data.invite_link;
  const copy = async (text: string) => { await Clipboard.setStringAsync(text); Alert.alert(t('Скопировано'), text); };
  const startEdit = () => setEdit({ title: data.title, about: data.about, is_public: data.public, handle: data.handle, only_admins_post: data.only_admins_post,
    protected: !!data.protected, reactions_on: data.reactions_on !== false, comments_on: !!data.comments_on, slow_seconds: data.slow_seconds ?? 0 });
  const slowName = (sec: number) => (!sec ? t('Выкл.') : sec < 60 ? t('{n} с', { n: sec }) : sec < 3600 ? t('{n} мин', { n: sec / 60 }) : t('1 час'));
  const actions: Action[] = !data.member ? [] : [
    { icon: 'chatbubble', label: t('Чат'), onPress: () => router.push(`/chat/${id}`) },
    { icon: data.muted ? 'notifications-off' : 'notifications', label: data.muted ? t('Без звука') : t('Звук'), off: data.muted, onPress: () => act(data.muted ? 'unmute' : 'mute') },
    ...(link ? [{ icon: 'share-social' as const, label: t('Ссылка'), onPress: () => { Share.share({ message: `${data.title}\n${link}` }); } }] : []),
    ...(data.admin ? [{ icon: 'pencil' as const, label: t('Изменить'), onPress: startEdit }] : []),
  ];
  // редкое и опасное — в меню «⋮», как в Telegram, а не большой кнопкой внизу
  const items: SheetItem[] = [
    ...(data.admin && data.invite_link ? [{ icon: 'refresh-outline' as const, title: t('Сделать новую ссылку'), subtitle: t('Старая перестанет работать'), onPress: () => act('invite', t('Старая ссылка перестанет работать. Продолжить?')) }] : []),
    ...(!data.admin ? [{ icon: 'flag-outline' as const, title: t('Пожаловаться'), onPress: () => router.push({ pathname: '/report', params: { type: 'thread', id: String(id) } }) }] : []),
    ...(data.member && !owner ? [{ icon: 'exit-outline' as const, danger: true, title: channel ? t('Отписаться') : t('Выйти из группы'), onPress: () => act('leave', t('Выйти?')) }] : []),
    ...(owner ? [{ icon: 'trash-outline' as const, danger: true, title: channel ? t('Удалить канал') : t('Удалить группу'), onPress: () => act('delete', t('Удалить навсегда вместе со всеми сообщениями?')) }] : []),
  ];
  const row = (icon: any, value: string, label: string, onPress?: () => void, first = false, accent = false) => (
    <Pressable onPress={onPress} disabled={!onPress} style={({ pressed }) => ({ flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 10, paddingHorizontal: 16,
      borderTopWidth: first ? 0 : 0.5, borderTopColor: c.line, backgroundColor: pressed ? c.card2 : 'transparent' })}>
      <Icon name={icon} size={21} color={c.inkSoft} />
      <View style={{ flex: 1 }}>
        <Txt style={{ fontSize: 15.5, fontWeight: '600' }} color={accent ? c.accent : c.ink}>{value}</Txt>
        <Txt kind="small" style={{ fontSize: 12.5 }}>{label}</Txt>
      </View>
    </Pressable>
  );
  const short = (u: string) => u.replace(/^https?:\/\//, '');

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top']}>
      <OfflineBar />
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 10, paddingTop: 4 }}>
        <Pressable onPress={() => (router.canGoBack() ? router.back() : router.replace('/chats'))} hitSlop={12} style={{ padding: 4 }}><Icon name="chevron-back" size={27} color={c.accent} /></Pressable>
        {items.length ? <Pressable onPress={() => setMenu(true)} hitSlop={12} style={{ padding: 6 }} accessibilityLabel={t('Ещё')}><Icon name="ellipsis-vertical" size={21} color={c.ink} /></Pressable> : null}
      </View>
      <ScrollView contentContainerStyle={{ padding: 16, paddingTop: 0, gap: 14, paddingBottom: 48 }} keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={loading} onRefresh={reload} tintColor={c.accent} />}>
        <ProfileHead name={data.title} avatar={data.avatar} hue={data.id} verified={data.verified} onAvatar={data.avatar ? () => setPhoto(0) : undefined}
          status={(channel ? t('канал · подписчиков: {n}', { n: data.members }) : t('группа · участников: {n}', { n: data.members })) + (data.closed ? ` · ${t('закрыт модератором')}` : '')} />
        {!data.member ? <Button title={channel ? t('Подписаться') : t('Вступить в группу')} onPress={() => act('join')} loading={busy} /> : <ProfileActions items={actions} />}

        <View style={{ backgroundColor: c.card, borderRadius: 20, overflow: 'hidden', paddingVertical: 2 }}>
          {data.about ? row('information-circle-outline', data.about, t('Описание'), undefined, true) : null}
          {data.public_link ? row('at-outline', short(data.public_link), t('Публичная ссылка — открыта всем'), () => copy(data.public_link), !data.about) : null}
          {data.invite_link ? row('link-outline', short(data.invite_link), t('Ссылка-приглашение — только для тех, кому вы её дали'), () => copy(data.invite_link), !data.about && !data.public_link) : null}
          {data.admin && !data.public_link ? row('at-outline', t('Сделать публичную ссылку'), t('Короткий адрес — чат появится в каталоге'), startEdit, !data.about && !data.invite_link, true) : null}
        </View>

        {edit ? (
          <Card style={{ gap: 12 }}>
            <Field label={t('Название')} value={edit.title} onChangeText={(x) => setEdit({ ...edit, title: x })} maxLength={120} />
            <Field label={t('Описание')} value={edit.about} onChangeText={(x) => setEdit({ ...edit, about: x })} maxLength={500} multiline />
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Txt style={{ flex: 1 }}>{t('Виден в каталоге, вступить может любой')}</Txt>
              <Switch value={edit.is_public} onValueChange={(x) => setEdit({ ...edit, is_public: x })} trackColor={{ true: c.accent, false: c.line }} />
            </View>
            {edit.is_public ? (
              <View style={{ gap: 4 }}>
                <Field label={t('Публичное имя')} value={edit.handle} onChangeText={(x) => setEdit({ ...edit, handle: x.toLowerCase() })} autoCapitalize="none" autoCorrect={false} maxLength={32} placeholder="masjid_nur" />
                <Txt kind="small">{t('Латинские буквы (a–z), цифры и «_», от 3 знаков. Например: masjid_nur или ilm2024. По этому адресу чат находят и делятся им.')}</Txt>
              </View>
            ) : null}
            {!channel ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <Txt style={{ flex: 1 }}>{t('Писать могут только админы')}</Txt>
                <Switch value={edit.only_admins_post} onValueChange={(x) => setEdit({ ...edit, only_admins_post: x })} trackColor={{ true: c.accent, false: c.line }} />
              </View>
            ) : null}
            {!channel ? (
              <View style={{ gap: 6 }}>
                <Txt style={{ fontWeight: '600' }}>{t('Медленный режим')}</Txt>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                  {SLOW.map((sec) => (
                    <Pressable key={sec} onPress={() => setEdit({ ...edit, slow_seconds: sec })}
                      style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, backgroundColor: edit.slow_seconds === sec ? c.accent : c.card2 }}>
                      <Txt kind="small" color={edit.slow_seconds === sec ? '#fff' : c.ink} style={{ fontWeight: '700' }}>{slowName(sec)}</Txt>
                    </Pressable>
                  ))}
                </View>
                <Txt kind="small">{t('Участник пишет не чаще, чем раз в выбранное время. На админов не действует.')}</Txt>
              </View>
            ) : null}
            {([...(channel ? [['comments_on', t('Комментарии под постами')]] : []), ['reactions_on', t('Реакции на сообщения')],
              ['protected', t('Запретить пересылку и копирование')]] as [keyof Edit, string][]).map(([key, label]) => (
              <View key={key} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <Txt style={{ flex: 1 }}>{label}</Txt>
                <Switch value={!!edit[key]} onValueChange={(x) => setEdit({ ...edit, [key]: x })} trackColor={{ true: c.accent, false: c.line }} />
              </View>
            ))}
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <Button kind="ghost" style={{ flex: 1 }} title={t('Отмена')} onPress={() => setEdit(null)} />
              <Button style={{ flex: 1 }} title={t('Сохранить')} onPress={save} loading={busy} />
            </View>
          </Card>
        ) : null}

        {data.people.length ? (
          <Section title={`${channel ? t('Подписчики') : t('Участники')} · ${data.members}`}>
            <View style={{ backgroundColor: c.card, borderRadius: 20, overflow: 'hidden' }}>
              {data.people.map((p, i) => (
                <Press key={p.id} onPress={() => setWho(p)} scale={0.985}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 8, paddingHorizontal: 14, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
                  <Avatar uri={p.avatar} name={p.name} size={42} hue={p.id} />
                  <View style={{ flex: 1 }}>
                    <Txt style={{ fontWeight: '700', fontSize: 15.5 }} numberOfLines={1}>{p.name}</Txt>
                    {p.role !== 'member' ? <Txt kind="small" color={c.accent}>{p.role_name}</Txt> : null}
                  </View>
                </Press>
              ))}
            </View>
          </Section>
        ) : null}
      </ScrollView>
      <Sheet open={menu} onClose={() => setMenu(false)} title={data.title} items={items} />
      <Sheet open={!!who} onClose={() => setWho(null)} title={who?.name} items={who ? memberMenu(who) : []} />
      <PhotoViewer photos={data.avatar ? [{ url: data.avatar, name: data.title }] : []} index={photo} onClose={() => setPhoto(null)} />
    </SafeAreaView>
  );
}
