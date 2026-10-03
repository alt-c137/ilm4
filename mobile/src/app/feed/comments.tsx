import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, FlatList, KeyboardAvoidingView, Platform, Pressable, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { ago } from '@/ui/feed';
import { Avatar, Icon, Loading, OfflineBar, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type C = { id: number; text: string; created: string; hue: number; user: { id: number; name: string; avatar: string }; reply_to: string; mine: boolean };

/** Комментарии к записи или публикации в ленте. */
export default function Comments() {
  const { target } = useLocalSearchParams<{ target: string }>();
  const { c, t, lang, user } = useApp();
  const url = `/feed/comments/?target=${encodeURIComponent(target ?? '')}`;
  const { data, setData, loading } = useFetch<{ items: C[] }>(url);
  const [text, setText] = useState('');
  const [to, setTo] = useState<C | null>(null);
  const send = async () => {
    if (!text.trim()) return;
    try {
      setData(await api<{ items: C[] }>('/feed/comments/', { body: { target, text, reply_to: to?.id ?? '' } }));
      setText('');
      setTo(null);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const remove = (x: C) => Alert.alert(t('Удалить комментарий?'), undefined, [
    { text: t('Отмена'), style: 'cancel' },
    { text: t('Удалить'), style: 'destructive', onPress: async () => {
      await api(`/feed/comment/${x.id}/delete/`, { body: {} }).catch(() => {});
      setData({ items: (data?.items ?? []).filter((y) => y.id !== x.id) });
    } },
  ]);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top', 'bottom']}>
      <OfflineBar />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, padding: 10 }}>
        <Pressable onPress={() => router.back()} hitSlop={10}><Icon name="chevron-back" size={27} color={c.accent} /></Pressable>
        <Txt kind="h3">{t('Комментарии')}{data?.items.length ? ` · ${data.items.length}` : ''}</Txt>
      </View>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        {!data && loading ? <Loading /> : (
          <FlatList data={data?.items ?? []} keyExtractor={(x) => String(x.id)} contentContainerStyle={{ padding: 12, gap: 12 }}
            ListEmptyComponent={<Txt kind="muted" style={{ textAlign: 'center', padding: 24 }}>{t('Комментариев пока нет — напишите первым.')}</Txt>}
            renderItem={({ item: x }) => (
              <View style={{ flexDirection: 'row', gap: 10 }}>
                <Pressable onPress={() => router.push(`/user/${x.user.id}`)}><Avatar uri={x.user.avatar} name={x.user.name} size={36} hue={x.hue} /></Pressable>
                <View style={{ flex: 1, gap: 2 }}>
                  <Txt style={{ fontWeight: '700' }}>{x.user.name}{x.reply_to ? <Txt kind="small"> → {x.reply_to}</Txt> : null}</Txt>
                  <Txt style={{ fontSize: 15, lineHeight: 21 }}>{x.text}</Txt>
                  <View style={{ flexDirection: 'row', gap: 14 }}>
                    <Txt kind="small">{ago(x.created, t, lang)}</Txt>
                    {user ? <Pressable onPress={() => setTo(x)} hitSlop={6}><Txt kind="small" color={c.accentD} style={{ fontWeight: '700' }}>{t('Ответить')}</Txt></Pressable> : null}
                    {x.mine ? <Pressable onPress={() => remove(x)} hitSlop={6}><Txt kind="small" color={c.bad} style={{ fontWeight: '700' }}>{t('Удалить')}</Txt></Pressable> : null}
                  </View>
                </View>
              </View>
            )} />
        )}
        {user ? (
          <View style={{ backgroundColor: c.card, borderTopWidth: 0.5, borderTopColor: c.line, padding: 8, gap: 4 }}>
            {to ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 8 }}>
                <Txt kind="small" color={c.accentD} style={{ flex: 1, fontWeight: '700' }}>↩ {to.user.name}</Txt>
                <Pressable onPress={() => setTo(null)} hitSlop={10}><Icon name="close" size={18} color={c.inkSoft} /></Pressable>
              </View>
            ) : null}
            <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
              <TextInput value={text} onChangeText={setText} multiline maxLength={2000} placeholder={t('Комментарий')} placeholderTextColor={c.inkSoft}
                style={{ flex: 1, minHeight: 44, maxHeight: 120, backgroundColor: c.card2, borderRadius: 22, borderWidth: 1, borderColor: c.line, paddingHorizontal: 16, paddingTop: 11, paddingBottom: 11, fontSize: 16, color: c.ink }} />
              <Pressable onPress={send} disabled={!text.trim()} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: text.trim() ? c.accent : c.line, alignItems: 'center', justifyContent: 'center' }}>
                <Icon name="send" size={19} color="#fff" />
              </Pressable>
            </View>
          </View>
        ) : null}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
