import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, Share, TextInput, View } from 'react-native';

import { api, ApiError, API_URL } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Button, Card, Empty, ErrorBox, Icon, Loading, Screen, Sheet, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type Person = { id: number; name: string; handle: string; avatar: string; online: boolean; status: string; verified: boolean };

/** «Контакты» — как в Telegram: сохранённые люди, поиск, «Добавить контакт» (имя, фамилия, номер), «Пригласить друзей». */
export default function Contacts() {
  const { c, t } = useApp();
  const { data, setData, loading, error, reload } = useFetch<{ items: Person[] }>('/contacts/');
  const [q, setQ] = useState('');
  const [add, setAdd] = useState(false);
  const [first, setFirst] = useState('');
  const [last, setLast] = useState('');
  const [phone, setPhone] = useState('');
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState<Person | null>(null);

  const post = async (body: Record<string, unknown>) => {
    setBusy(true);
    try {
      setData(await api<{ items: Person[] }>('/contacts/', { body }));
      return true;
    } catch (e) {
      Alert.alert((e as ApiError).message);
      return false;
    } finally {
      setBusy(false);
    }
  };
  const save = async () => { if (await post({ first_name: first, last_name: last, phone })) { setAdd(false); setFirst(''); setLast(''); setPhone(''); } };
  const open = async (p: Person) => {
    try {
      const r = await api<{ thread: number }>(`/users/${p.id}/chat/`, { body: {} });
      router.push(`/chat/${r.thread}`);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const needle = q.trim().toLowerCase();
  const items = (data?.items ?? []).filter((p) => !needle || `${p.name} ${p.handle}`.toLowerCase().includes(needle));
  const input = { backgroundColor: c.card2, borderRadius: 14, padding: 12, fontSize: 16, color: c.ink };
  const action = (icon: 'person-add' | 'paper-plane', title: string, sub: string, onPress: () => void) => (
    <Pressable onPress={onPress} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 8 }}>
      <View style={{ width: 46, height: 46, borderRadius: 23, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}><Icon name={icon} size={21} color={c.accentD} /></View>
      <View style={{ flex: 1 }}><Txt style={{ fontWeight: '700', fontSize: 16 }}>{title}</Txt><Txt kind="small">{sub}</Txt></View>
    </Pressable>
  );

  return (
    <Screen title={t('Контакты')} back onRefresh={reload} refreshing={loading && !!data}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: c.card, borderRadius: 14, paddingHorizontal: 12, height: 44 }}>
        <Icon name="search" size={18} color={c.inkSoft} />
        <TextInput value={q} onChangeText={setQ} placeholder={t('Поиск')} placeholderTextColor={c.inkSoft} style={{ flex: 1, fontSize: 16, color: c.ink }} autoCorrect={false} />
      </View>
      <Card style={{ paddingVertical: 4 }}>
        {action('person-add', t('Добавить контакт'), t('По номеру телефона'), () => setAdd(true))}
        {action('paper-plane', t('Пригласить друзей'), t('Отправить ссылку на ilm4'), () => { Share.share({ message: API_URL }); })}
      </Card>
      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : items.length ? (
        <Card style={{ paddingVertical: 4 }}>
          {items.map((p, i) => (
            <Pressable key={p.id} onPress={() => open(p)} onLongPress={() => setMenu(p)} delayLongPress={350}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 9, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
              <Avatar uri={p.avatar} name={p.name} size={46} hue={p.id} online={p.online} />
              <View style={{ flex: 1 }}>
                <Txt style={{ fontWeight: '700', fontSize: 16 }} numberOfLines={1}>{p.name}</Txt>
                <Txt kind="small" color={p.online ? c.accent : undefined} numberOfLines={1}>{p.online ? t('в сети') : p.status}</Txt>
              </View>
            </Pressable>
          ))}
        </Card>
      ) : (
        <Empty icon="people-outline" title={needle ? t('Ничего не найдено') : t('Контактов пока нет')}
          text={t('Добавьте человека по номеру — или нажмите «Добавить в контакты» в его профиле.')} />
      )}
      <Sheet open={add} onClose={() => setAdd(false)} title={t('Новый контакт')} items={[]} header={
        <View style={{ paddingHorizontal: 20, gap: 10, paddingBottom: 10 }}>
          <TextInput value={first} onChangeText={setFirst} placeholder={t('Имя')} placeholderTextColor={c.inkSoft} maxLength={60} style={input} />
          <TextInput value={last} onChangeText={setLast} placeholder={t('Фамилия (необязательно)')} placeholderTextColor={c.inkSoft} maxLength={60} style={input} />
          <TextInput value={phone} onChangeText={setPhone} placeholder="+998 90 123 45 67" placeholderTextColor={c.inkSoft} keyboardType="phone-pad" style={input} />
          <Txt kind="small">{t('Найдётся только тот, кто подтвердил номер и разрешил находить себя по нему. Сам номер нигде не показывается.')}</Txt>
          <Button title={t('Добавить')} onPress={save} loading={busy} disabled={!first.trim() || phone.replace(/\D/g, '').length < 9} />
        </View>} />
      <Sheet open={!!menu} onClose={() => setMenu(null)} title={menu?.name} items={menu ? [
        { icon: 'person-outline', title: t('Профиль'), onPress: () => router.push(`/user/${menu.id}`) },
        { icon: 'trash-outline', danger: true, title: t('Удалить контакт'), onPress: () => post({ remove: menu.id }) },
      ] : []} />
    </Screen>
  );
}
