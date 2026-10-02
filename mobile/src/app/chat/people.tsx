import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Alert, FlatList, Pressable, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Icon, OfflineBar, Press, Txt, type IconName } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type Person = { id: number; name: string; handle: string; avatar: string; city: string; verified: boolean; online: boolean };
type Found = { items: Person[]; contacts: Person[]; hint: string };
type Row = { kind: 'head'; key: string; title: string } | { kind: 'person'; key: string; p: Person } | { kind: 'act'; key: string; icon: IconName; title: string; sub: string; go: () => void };

/** «Новое сообщение» — как в Telegram: найти человека по @имени или номеру, свои контакты, новая группа / канал. */
export default function People() {
  const { c, t, config } = useApp();
  const { data: base } = useFetch<Found & { can?: boolean }>('/people/');
  const { data: chats } = useFetch<{ support: boolean; can_group: boolean; can_channel: boolean; channels: boolean }>('/chat/');
  const [q, setQ] = useState('');
  const [found, setFound] = useState<Found | null>(null);
  const [busy, setBusy] = useState(false);
  const [opening, setOpening] = useState(0);
  const seq = useRef(0);

  // поиск — после паузы в наборе, чтобы не дёргать сервер на каждую букву
  useEffect(() => {
    const text = q.trim();
    const my = ++seq.current;
    if (text.length < 3) return;
    const timer = setTimeout(async () => {
      setBusy(true);
      try {
        const r = await api<Found>(`/people/?q=${encodeURIComponent(text)}`);
        if (my === seq.current) setFound(r);
      } catch (e) {
        if (my === seq.current) setFound({ items: [], contacts: [], hint: (e as ApiError).message });
      } finally {
        if (my === seq.current) setBusy(false);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [q]);

  const open = async (p: Person) => {
    if (opening) return;
    setOpening(p.id);
    try {
      const r = await api<{ thread: number }>(`/users/${p.id}/chat/`, { body: {} });
      router.replace(`/chat/${r.thread}`);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    } finally {
      setOpening(0);
    }
  };
  const support = async () => {
    try {
      const r = await api('/chat/support/', { body: {} });
      router.replace(`/chat/${r.thread}`);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };

  const searching = q.trim().length >= 3;
  const rows: Row[] = [];
  if (searching) {
    if (found?.items.length) rows.push({ kind: 'head', key: 'h1', title: t('Найдены') }, ...found.items.map((p) => ({ kind: 'person' as const, key: `f${p.id}`, p })));
    if (found?.contacts.length) rows.push({ kind: 'head', key: 'h2', title: t('Из ваших чатов') }, ...found.contacts.map((p) => ({ kind: 'person' as const, key: `c${p.id}`, p })));
  } else {
    if (chats?.can_group) rows.push({ kind: 'act', key: 'g', icon: 'people', title: t('Новая группа'), sub: t('Общий чат: семья, община, соседи'), go: () => router.push({ pathname: '/chat/new', params: { kind: 'group' } }) });
    if (chats?.can_channel) rows.push({ kind: 'act', key: 'ch', icon: 'megaphone', title: t('Новый канал'), sub: t('Лента для мечети, учителя, магазина'), go: () => router.push({ pathname: '/chat/new', params: { kind: 'channel' } }) });
    if (chats?.channels ?? config?.features.channels) rows.push({ kind: 'act', key: 'cat', icon: 'search', title: t('Найти каналы и группы'), sub: t('Каталог открытых каналов и групп'), go: () => router.push('/chat/channels') });
    if (chats?.support) rows.push({ kind: 'act', key: 's', icon: 'help-buoy', title: t('Поддержка ilm4'), sub: t('Написать команде площадки'), go: support });
    if (base?.contacts.length) rows.push({ kind: 'head', key: 'h3', title: t('Контакты') }, ...base.contacts.map((p) => ({ kind: 'person' as const, key: `k${p.id}`, p })));
  }
  const hint = searching ? (found && !rows.length ? found.hint || t('Никого не нашли.') : '')
    : q.trim() ? t('Введите хотя бы 3 знака.')
      : !base?.contacts.length ? t('Контактов пока нет: здесь появятся люди, с которыми вы переписывались.') : '';

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top']}>
      <OfflineBar />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 10, paddingRight: 14, paddingVertical: 8 }}>
        <Pressable onPress={() => (router.canGoBack() ? router.back() : router.replace('/chats'))} hitSlop={12} style={{ padding: 2 }}>
          <Icon name="chevron-back" size={27} color={c.accent} />
        </Pressable>
        <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8, height: 44, borderRadius: 22, backgroundColor: c.card, borderWidth: 1, borderColor: c.line, paddingHorizontal: 14 }}>
          <Icon name="search" size={18} color={c.inkSoft} />
          <TextInput value={q} onChangeText={setQ} autoFocus autoCapitalize="none" autoCorrect={false} returnKeyType="search"
            placeholder={t('Имя пользователя или номер')} placeholderTextColor={c.inkSoft} style={{ flex: 1, fontSize: 16, color: c.ink, paddingVertical: 0 }} />
          {busy ? <ActivityIndicator color={c.accent} /> : q ? <Pressable onPress={() => setQ('')} hitSlop={10}><Icon name="close-circle" size={18} color={c.inkSoft} /></Pressable> : null}
        </View>
      </View>
      <FlatList
        data={rows}
        keyExtractor={(r) => r.key}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ paddingBottom: 40 }}
        ListHeaderComponent={!q ? <Txt kind="small" style={{ paddingHorizontal: 18, paddingBottom: 6 }}>{t('Найдите человека по @имени или по номеру — и сразу пишите.')}</Txt> : null}
        ListFooterComponent={hint ? <Txt kind="muted" style={{ textAlign: 'center', padding: 28 }}>{hint}</Txt> : null}
        renderItem={({ item: r }) => {
          if (r.kind === 'head') return <Txt kind="label" style={{ paddingHorizontal: 18, paddingTop: 16, paddingBottom: 6 }}>{r.title}</Txt>;
          if (r.kind === 'act') {
            return (
              <Press onPress={r.go} scale={0.985} style={{ flexDirection: 'row', alignItems: 'center', gap: 13, paddingVertical: 8, paddingHorizontal: 16 }}>
                <View style={{ width: 50, height: 50, borderRadius: 25, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name={r.icon} size={23} color={c.accent} />
                </View>
                <View style={{ flex: 1 }}>
                  <Txt style={{ fontSize: 16.5, fontWeight: '700' }}>{r.title}</Txt>
                  <Txt kind="small" numberOfLines={1}>{r.sub}</Txt>
                </View>
              </Press>
            );
          }
          const p = r.p;
          return (
            <Press onPress={() => open(p)} onLongPress={() => router.push(`/user/${p.id}`)} scale={0.985}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 13, paddingVertical: 8, paddingHorizontal: 16 }}>
              <Pressable onPress={() => router.push(`/user/${p.id}`)} hitSlop={4}><Avatar uri={p.avatar} name={p.name} size={50} hue={p.id} online={p.online} /></Pressable>
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
                  <Txt style={{ fontSize: 16.5, fontWeight: '700', flexShrink: 1 }} numberOfLines={1}>{p.name}</Txt>
                  {p.verified ? <Icon name="checkmark-circle" size={15} color={c.accent} /> : null}
                </View>
                <Txt kind="small" numberOfLines={1} color={p.online ? c.accent : c.inkSoft}>
                  {[p.online ? t('в сети') : '', p.handle ? `@${p.handle}` : '', !p.online && !p.handle ? p.city || t('на ilm4') : ''].filter(Boolean).join(' · ')}</Txt>
              </View>
              {opening === p.id ? <ActivityIndicator color={c.accent} /> : null}
            </Press>
          );
        }}
      />
    </SafeAreaView>
  );
}
