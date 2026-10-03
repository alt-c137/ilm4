import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, ApiError, authHeaders, chatFileUrl } from '@/lib/api';
import { useApp } from '@/state/app';
import type { Msg } from '@/ui/bubble';
import { Avatar, ErrorBox, Icon, Loading, OfflineBar, Txt } from '@/ui/kit';
import { Rich } from '@/ui/rich';
import { useFetch } from '@/ui/useFetch';

type Data = { post: Msg; items: Msg[]; can_write: boolean };

/** Комментарии под постом канала — как обсуждение поста в Telegram. */
export default function PostComments() {
  const { id, thread } = useLocalSearchParams<{ id: string; thread: string }>();
  const { c, t, user } = useApp();
  const url = `/chat/${thread}/post/${id}/`;
  const { data, setData, loading, error, reload } = useFetch<Data>(url);
  const [text, setText] = useState('');
  const [replyTo, setReplyTo] = useState<Msg | null>(null);
  const [busy, setBusy] = useState(false);

  const send = async () => {
    const body = text.trim();
    if (!body || busy) return;
    setBusy(true);
    try {
      setData(await api<Data>(url, { body: { body, reply_to: replyTo?.id ?? '' } }));
      setText('');
      setReplyTo(null);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };
  const remove = (m: Msg) => Alert.alert(t('Удалить комментарий?'), undefined, [
    { text: t('Отмена'), style: 'cancel' },
    { text: t('Удалить'), style: 'destructive', onPress: async () => {
      try {
        await api(`/chat/msg/${m.id}/delete/`, { body: {} });
        reload(true);
      } catch (e) {
        Alert.alert((e as ApiError).message);
      }
    } },
  ]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top', 'bottom']}>
      <OfflineBar />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 8 }}>
        <Pressable onPress={() => (router.canGoBack() ? router.back() : router.replace(`/chat/${thread}`))} hitSlop={10} style={{ padding: 4 }}>
          <Icon name="chevron-back" size={27} color={c.accent} />
        </Pressable>
        <Txt kind="h3" style={{ flex: 1 }}>{t('Комментарии')}{data?.items.length ? ` · ${data.items.length}` : ''}</Txt>
      </View>
      {!data ? (loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />) : (
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView contentContainerStyle={{ padding: 12, gap: 10, paddingBottom: 24 }} keyboardShouldPersistTaps="handled">
            <View style={{ backgroundColor: c.card, borderRadius: 20, padding: 14, gap: 8 }}>
              {data.post.kind === 'photo' ? <Image source={{ uri: chatFileUrl(data.post.id), headers: authHeaders() }} style={{ width: '100%', height: 220, borderRadius: 14, backgroundColor: c.card2 }} contentFit="cover" /> : null}
              {data.post.body ? <Txt style={{ fontSize: 16, lineHeight: 22 }}><Rich text={data.post.body} color={c.ink} /></Txt> : null}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
                <Icon name="eye-outline" size={14} color={c.inkSoft} />
                <Txt kind="small">{data.post.views ?? 0} · {data.post.time}</Txt>
              </View>
            </View>
            {data.items.length ? data.items.map((m) => (
              <View key={m.id} style={{ flexDirection: 'row', gap: 9 }}>
                <Pressable onPress={() => router.push(`/user/${m.sender_id}`)}><Avatar name={m.sender_name} size={36} hue={m.hue ?? 0} /></Pressable>
                <View style={{ flex: 1, backgroundColor: c.card, borderRadius: 16, paddingHorizontal: 12, paddingVertical: 8, gap: 2 }}>
                  <Txt kind="small" color={c.accentD} style={{ fontWeight: '700' }}>{m.sender_name}</Txt>
                  {m.reply ? <Txt kind="small" numberOfLines={1}>↩ {m.reply.name}: {m.reply.text}</Txt> : null}
                  <Txt style={{ fontSize: 15.5, lineHeight: 21 }}><Rich text={m.body} color={c.ink} /></Txt>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 2 }}>
                    <Txt kind="small" style={{ fontSize: 12 }}>{m.time}</Txt>
                    {data.can_write ? <Pressable hitSlop={8} onPress={() => setReplyTo(m)}><Txt kind="small" color={c.accentD} style={{ fontWeight: '700', fontSize: 12.5 }}>{t('Ответить')}</Txt></Pressable> : null}
                    {m.sender_id === user?.id ? <Pressable hitSlop={8} onPress={() => remove(m)}><Txt kind="small" color={c.bad} style={{ fontWeight: '700', fontSize: 12.5 }}>{t('Удалить')}</Txt></Pressable> : null}
                  </View>
                </View>
              </View>
            )) : <Txt kind="muted" style={{ textAlign: 'center', padding: 22 }}>{t('Комментариев пока нет — напишите первым.')}</Txt>}
          </ScrollView>
          {data.can_write ? (
            <View style={{ backgroundColor: c.card, borderTopWidth: 0.5, borderTopColor: c.line, paddingHorizontal: 8, paddingVertical: 7, gap: 4 }}>
              {replyTo ? (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 8 }}>
                  <Txt kind="small" color={c.accentD} style={{ flex: 1, fontWeight: '700' }} numberOfLines={1}>↩ {replyTo.sender_name}</Txt>
                  <Pressable hitSlop={10} onPress={() => setReplyTo(null)}><Icon name="close" size={18} color={c.inkSoft} /></Pressable>
                </View>
              ) : null}
              <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
                <TextInput value={text} onChangeText={setText} multiline maxLength={2000} placeholder={t('Комментарий')} placeholderTextColor={c.inkSoft}
                  style={{ flex: 1, minHeight: 46, maxHeight: 120, backgroundColor: c.card2, borderRadius: 23, borderWidth: 1, borderColor: c.line, paddingHorizontal: 16,
                    paddingTop: Platform.OS === 'ios' ? 12 : 9, paddingBottom: Platform.OS === 'ios' ? 12 : 9, fontSize: 16, color: c.ink }} />
                <Pressable onPress={send} disabled={!text.trim() || busy} style={{ width: 46, height: 46, borderRadius: 23, backgroundColor: text.trim() ? c.accent : c.line, alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name="send" size={20} color="#fff" />
                </Pressable>
              </View>
            </View>
          ) : (
            <View style={{ padding: 12, backgroundColor: c.card }}><Txt kind="muted" style={{ textAlign: 'center' }}>{t('Комментировать могут подписчики канала.')}</Txt></View>
          )}
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
  );
}
