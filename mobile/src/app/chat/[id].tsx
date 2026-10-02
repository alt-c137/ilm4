import * as DocumentPicker from 'expo-document-picker';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { usePreventScreenCapture } from 'expo-screen-capture';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, FlatList, KeyboardAvoidingView, Platform, Pressable, View } from 'react-native';
import Animated, { FadeInDown, ZoomOut } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, authHeaders, cachedGet, chatFileUrl, wsUrl } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Icon, OfflineBar, Txt } from '@/ui/kit';
import { callsSupported } from '@/lib/webrtc';
import { setOpenThread } from '@/state/calls';
import { CallView, type CallHandle } from '@/ui/call';
import { Composer, type SendOpts } from '@/ui/composer';
import { openSiteUrl } from '@/lib/links';
import { ChatFile, ChatPhoto, ChatVideo, ChatVoice } from '@/ui/media';

type Msg = { id: number; sender_id: number; sender_name: string; kind: string; body: string; url: string; duration: number; time: string; day: string;
  mine?: boolean; read?: boolean; scheduled?: boolean; scheduled_label?: string; silent?: boolean;
  file_name?: string; file_size?: number; warn?: boolean };
type CtxCard = { title: string; label: string; price: string; image: string; url: string; closed: boolean; closed_text: string;
  actions: { kind: string; label: string; text: string }[] };
type Thread = { id: number; title: string; subject: string; other_id: number | null; avatar: string; blocked: boolean; nikah: boolean;
  turn: { url: string; username: string; credential: string } | null;
  witnesses: string[]; features: Record<string, any>; card: CtxCard | null; notice: string; warn_text: string };

function NoScreenshots() {
  usePreventScreenCapture('nikah-chat');
  return null;
}

export default function ChatScreen() {
  const { id, answer } = useLocalSearchParams<{ id: string; answer?: string }>();
  const { c, t, user } = useApp();
  const [items, setItems] = useState<Msg[]>([]);
  const [thread, setThread] = useState<Thread | null>(null);
  const [more, setMore] = useState(false);
  const [uploading, setUploading] = useState(false);
  const call = useRef<CallHandle>(null);
  const ws = useRef<WebSocket | null>(null);
  const initial = useRef<Set<number> | null>(null);   // загруженные сразу — без анимации появления

  const norm = useCallback((m: Msg): Msg => ({
    ...m, mine: m.sender_id === user?.id, url: ['photo', 'video', 'voice', 'circle', 'file'].includes(m.kind) ? chatFileUrl(m.id) : '',
  }), [user?.id]);

  // новое сообщение; запланированное, которое ушло, — заменяем и переносим в конец
  const add = useCallback((m: Msg) => setItems((old) => {
    const prev = old.find((x) => x.id === m.id);
    if (prev && !(prev.scheduled && !m.scheduled)) return old;
    return [...old.filter((x) => x.id !== m.id), norm(m)];
  }), [norm]);

  const load = useCallback(async () => {
    try {
      const { data } = await cachedGet(`/chat/${id}/`);
      if (!initial.current) initial.current = new Set(data.items.map((m: Msg) => m.id));
      setItems(data.items.map(norm));
      setThread(data.thread);
      setMore(data.more);
    } catch (e: any) {
      Alert.alert(e.message);
    }
  }, [id, norm]);

  // этот диалог открыт — всплывашка «входящий звонок» не нужна, звонок покажет сам экран
  useEffect(() => {
    setOpenThread(Number(id));
    if (answer === '1') call.current?.answerNext();
    return () => setOpenThread(null);
  }, [id, answer]);

  const sendWs = useCallback((o: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(o));
  }, []);

  const startCall = (video: boolean) => {
    if (!callsSupported) {
      Alert.alert(t('Звонки'), t('Звонки работают в установленном приложении ilm4. В тестовом Expo Go их нет — это ограничение Expo Go.'));
      return;
    }
    call.current?.start(video);
  };

  // живые сообщения: тот же WebSocket, что у сайта; обрыв — переподключение
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- первая загрузка переписки
    load();
    let stop = false;
    let retry: ReturnType<typeof setTimeout>;
    if (Platform.OS === 'web') {
      // браузер не умеет заголовки у WebSocket — в веб-версии просто обновляем раз в 5 секунд
      const poll = setInterval(load, 5000);
      return () => clearInterval(poll);
    }
    const connect = () => {
      // @ts-expect-error — в React Native третий аргумент: заголовки
      const sock: WebSocket = new WebSocket(wsUrl(`/ws/chat/${id}/`), null, { headers: authHeaders() });
      ws.current = sock;
      sock.onmessage = (e) => {
        const d = JSON.parse(e.data);
        if (d.type === 'msg') add(d);
        else if (d.type === 'read') setItems((old) => old.map((m) => (d.ids.includes(m.id) ? { ...m, read: true } : m)));
        else if (d.type === 'error') Alert.alert(d.error);
        else if (d.type === 'signal') call.current?.onSignal(d);
      };
      sock.onclose = () => {
        if (!stop) retry = setTimeout(() => { load(); connect(); }, 3000);
      };
    };
    connect();
    return () => {
      stop = true;
      clearTimeout(retry);
      ws.current?.close();
    };
  }, [id, load, add]);

  const older = async () => {
    if (!more || !items.length) return;
    const r = await api(`/chat/${id}/?before=${items[0].id}`).catch(() => null);
    if (r) {
      setItems((old) => [...r.items.map(norm), ...old]);
      setMore(r.more);
    }
  };

  const sendText = async (body: string, opts: SendOpts = {}) => {
    try {
      if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify({ body, ...opts }));
      else add(await api(`/chat/${id}/send/`, { body: { body, ...opts } }));
      if (opts.schedule) Alert.alert(t('Сообщение запланировано'));
      return true;
    } catch (e: any) {
      Alert.alert(e.message);
      return false;
    }
  };

  const scheduledAction = async (m: Msg, action: 'send' | 'cancel') => {
    try {
      const r = await api(`/chat/msg/${m.id}/${action}/`, { body: {} });
      if (action === 'cancel') setItems((old) => old.filter((x) => x.id !== m.id));
      else add(r);
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };

  const upload = async (kind: string, uri: string, name: string, type: string, duration = 0) => {
    setUploading(true);
    try {
      const form = new FormData();
      form.append('kind', kind);
      form.append('duration', String(Math.round(duration)));
      form.append('file', { uri, name, type } as any);
      add(await api(`/chat/${id}/upload/`, { form, timeout: 120000 }));
    } catch (e: any) {
      Alert.alert(e.message);
    } finally {
      setUploading(false);
    }
  };

  const pick = async (camera: boolean) => {
    const f = thread?.features ?? {};
    const types: ImagePicker.MediaType[] = [...(f.photo ? ['images' as const] : []), ...(f.video ? ['videos' as const] : [])];
    if (!types.length) return;
    const perm = camera ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) return Alert.alert(t('Нет доступа'), t('Разрешите доступ в настройках телефона.'));
    // фото — сжимается; видео: iPhone сжимает до 720p перед отправкой, дальше сервер приводит к одному качеству
    const opts: ImagePicker.ImagePickerOptions = { mediaTypes: types, quality: 0.8, videoMaxDuration: 600,
      videoExportPreset: ImagePicker.VideoExportPreset.H264_1280x720 };
    const r = camera ? await ImagePicker.launchCameraAsync(opts) : await ImagePicker.launchImageLibraryAsync(opts);
    if (r.canceled || !r.assets[0]) return;
    const a = r.assets[0];
    if (a.type === 'video') {
      if (a.fileSize && a.fileSize > (f.file_max_mb || 100) * 1048576) return Alert.alert(t('Файл слишком большой'));
      return upload('video', a.uri, a.fileName || 'video.mp4', a.mimeType || 'video/mp4', (a.duration || 0) / 1000);
    }
    return upload('photo', a.uri, a.fileName || 'photo.jpg', a.mimeType || 'image/jpeg');
  };

  // «файлом» — без сжатия, в исходном качестве (как «Отправить файлом» в Telegram)
  const pickFile = async () => {
    const r = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true, multiple: false });
    if (r.canceled || !r.assets[0]) return;
    const a = r.assets[0];
    const max = (thread?.features.file_max_mb || 100) * 1048576;
    if (a.size && a.size > max) return Alert.alert(t('Файл слишком большой'));
    return upload('file', a.uri, a.name || 'file', a.mimeType || 'application/octet-stream');
  };

  const attach = () => {
    const ft = thread?.features ?? {};
    const media = ft.photo || ft.video;
    Alert.alert(t('Отправить'), ft.file ? t('Фото и видео сжимаются. «Файл» — без сжатия, в исходном качестве.') : undefined, [
      ...(media ? [{ text: t('Фото или видео'), onPress: () => Alert.alert(t('Фото или видео'), undefined, [
        { text: t('Из галереи'), onPress: () => pick(false) },
        { text: t('Снять камерой'), onPress: () => pick(true) },
        { text: t('Отмена'), style: 'cancel' as const },
      ]) }] : []),
      ...(ft.file ? [{ text: t('Файл (без сжатия)'), onPress: pickFile }] : []),
      { text: t('Отмена'), style: 'cancel' as const },
    ]);
  };

  const f = thread?.features ?? {};
  const canAttach = !!(f.photo || f.video || f.file);
  const data = [...items].reverse();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top', 'bottom']}>
      {thread?.nikah && Platform.OS !== 'web' ? <NoScreenshots /> : null}
      <OfflineBar />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, paddingVertical: 8, borderBottomWidth: 0.5, borderBottomColor: c.line, backgroundColor: c.card }}>
        <Pressable onPress={() => router.back()} hitSlop={12}><Icon name="chevron-back" size={26} color={c.accent} /></Pressable>
        <Avatar uri={thread?.avatar} name={thread?.title ?? ''} size={38} hue={thread?.other_id ?? 0} />
        <View style={{ flex: 1 }}>
          <Txt kind="h3" numberOfLines={1}>{thread?.title ?? ''}</Txt>
          {thread?.subject ? <Txt kind="small" numberOfLines={1}>{thread.subject}</Txt> : null}
        </View>
        {f.calls && !thread?.blocked && Platform.OS !== 'web' ? (
          <Pressable hitSlop={8} onPress={() => startCall(false)} style={{ paddingHorizontal: 4 }}><Icon name="call-outline" size={22} color={c.accent} /></Pressable>
        ) : null}
        {f.video_calls && !thread?.blocked && Platform.OS !== 'web' ? (
          <Pressable hitSlop={8} onPress={() => startCall(true)} style={{ paddingHorizontal: 4 }}><Icon name="videocam-outline" size={24} color={c.accent} /></Pressable>
        ) : null}
        {thread?.other_id ? (
          <Pressable hitSlop={10} onPress={() => router.push({ pathname: '/report', params: { type: 'user', id: String(thread.other_id), user_id: String(thread.other_id) } })}>
            <Icon name="ellipsis-vertical" size={22} color={c.inkSoft} />
          </Pressable>
        ) : null}
      </View>
      {thread?.nikah ? (
        <View style={{ backgroundColor: c.accentSoft, padding: 8, paddingHorizontal: 14 }}>
          <Txt kind="small" color={c.accentD}>{t('Чат никяха: помните об адабе. Контакты и ссылки не пропускаются, скриншоты запрещены.')}
            {thread.witnesses.length ? ' ' + t('Свидетели: {names}', { names: thread.witnesses.join(', ') }) : ''}</Txt>
        </View>
      ) : null}
      {thread?.card ? (
        <Pressable onPress={() => { if (thread.card?.url) openSiteUrl(thread.card.url); }}
          style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, paddingVertical: 8, backgroundColor: c.card,
            borderBottomWidth: 0.5, borderBottomColor: c.line, opacity: thread.card.closed ? 0.75 : 1 }}>
          {thread.card.image ? <Image source={{ uri: thread.card.image }} style={{ width: 44, height: 44, borderRadius: 10, backgroundColor: c.card2 }} contentFit="cover" /> : null}
          <View style={{ flex: 1 }}>
            <Txt kind="small" style={{ fontWeight: '700', textTransform: 'uppercase', fontSize: 11 }} numberOfLines={1}>
              {thread.card.label}{thread.card.closed ? ` · ${thread.card.closed_text}` : ''}</Txt>
            <Txt style={{ fontWeight: '700' }} numberOfLines={1}>{thread.card.title}</Txt>
            {thread.card.price ? <Txt kind="small" color={c.accentD} style={{ fontWeight: '800' }}>{thread.card.price}</Txt> : null}
          </View>
          {thread.card.actions.map((a) => (
            <Pressable key={a.label} onPress={() => sendText(a.text)} style={{ backgroundColor: c.accentSoft, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6 }}>
              <Txt kind="small" color={c.accentD} style={{ fontWeight: '700' }}>{a.label}</Txt>
            </Pressable>
          ))}
          {thread.card.url ? <Icon name="chevron-forward" size={18} color={c.inkSoft} /> : null}
        </Pressable>
      ) : null}
      {thread?.notice ? (
        <View style={{ flexDirection: 'row', gap: 8, backgroundColor: c.card2, paddingHorizontal: 12, paddingVertical: 7 }}>
          <Icon name="information-circle-outline" size={16} color={c.inkSoft} />
          <Txt kind="small" style={{ flex: 1 }}>{thread.notice}</Txt>
        </View>
      ) : null}
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <FlatList
          inverted
          data={data}
          keyExtractor={(m) => String(m.id)}
          onEndReached={older}
          contentContainerStyle={{ padding: 12, gap: 6 }}
          renderItem={({ item: m, index }) => {
            const prev = data[index + 1];
            const day = !prev || prev.day !== m.day ? m.day : '';
            return (
              <View>
                {day ? <Txt kind="small" style={{ textAlign: 'center', marginVertical: 8 }}>{day.split('-').reverse().join('.')}</Txt> : null}
                {m.kind === 'system' ? (
                  <View style={{ alignSelf: 'center', backgroundColor: c.card2, borderRadius: 12, paddingHorizontal: 10, paddingVertical: 5, maxWidth: '85%' }}>
                    <Txt kind="small" style={{ textAlign: 'center' }}>{m.body} · {m.time}</Txt>
                  </View>
                ) : (
                  <Animated.View
                    entering={initial.current?.has(m.id) ? undefined : FadeInDown.springify().damping(15)}
                    exiting={m.scheduled ? ZoomOut.duration(160) : undefined}
                    style={{
                      alignSelf: m.mine ? 'flex-end' : 'flex-start', maxWidth: '82%', backgroundColor: m.mine ? c.accent : c.card,
                      borderRadius: 18, borderBottomRightRadius: m.mine ? 6 : 18, borderBottomLeftRadius: m.mine ? 18 : 6,
                      padding: m.kind === 'text' || m.kind === 'voice' ? 10 : 4, gap: 4,
                      opacity: m.scheduled ? 0.85 : 1, borderWidth: m.scheduled ? 1.5 : 0, borderStyle: 'dashed',
                      borderColor: 'rgba(255,255,255,0.7)',
                    }}>
                    {m.kind === 'photo' ? <ChatPhoto uri={m.url} /> : null}
                    {m.kind === 'video' ? <ChatVideo uri={m.url} /> : null}
                    {m.kind === 'circle' ? <ChatVideo uri={m.url} round /> : null}
                    {m.kind === 'voice' ? <ChatVoice uri={m.url} duration={m.duration} mine={!!m.mine} /> : null}
                    {m.kind === 'file' ? <ChatFile uri={m.url} name={m.file_name ?? ''} size={m.file_size ?? 0} mine={!!m.mine} /> : null}
                    {m.body && m.kind !== 'voice' ? <Txt color={m.mine ? '#fff' : c.ink} style={{ paddingHorizontal: m.kind === 'text' ? 0 : 6 }} selectable>{m.body}</Txt> : null}
                    {m.scheduled ? (
                      <View style={{ gap: 6, paddingHorizontal: 4 }}>
                        <Txt kind="small" color="#fff" style={{ fontWeight: '700' }}>🕓 {m.scheduled_label}</Txt>
                        <View style={{ flexDirection: 'row', gap: 6 }}>
                          <Pressable onPress={() => scheduledAction(m, 'send')} style={{ backgroundColor: 'rgba(255,255,255,0.22)', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 }}>
                            <Txt kind="small" color="#fff">{t('Отправить сейчас')}</Txt>
                          </Pressable>
                          <Pressable onPress={() => scheduledAction(m, 'cancel')} style={{ backgroundColor: 'rgba(255,255,255,0.22)', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 }}>
                            <Txt kind="small" color="#fff">{t('Удалить')}</Txt>
                          </Pressable>
                        </View>
                      </View>
                    ) : (
                      <Txt kind="small" color={m.mine ? 'rgba(255,255,255,0.75)' : c.inkSoft} style={{ alignSelf: 'flex-end', fontSize: 11, paddingHorizontal: 4 }}>
                        {m.time}{m.mine ? (m.read ? ' ✓✓' : ' ✓') : ''}
                      </Txt>
                    )}
                  </Animated.View>
                )}
                {m.warn && !m.mine && thread?.warn_text ? (
                  <View style={{ alignSelf: 'flex-start', maxWidth: '82%', flexDirection: 'row', gap: 8, marginTop: 6, padding: 10, borderRadius: 14,
                    backgroundColor: '#fff4d6', borderWidth: 1, borderColor: '#f0d58a' }}>
                    <Icon name="shield-outline" size={17} color="#7a5600" />
                    <Txt kind="small" color="#7a5600" style={{ flex: 1, fontWeight: '600' }}>{thread.warn_text}</Txt>
                  </View>
                ) : null}
              </View>
            );
          }}
        />
        {thread?.blocked ? (
          <View style={{ padding: 16, backgroundColor: c.card }}><Txt kind="muted" style={{ textAlign: 'center' }}>{t('Переписка недоступна: один из вас заблокировал другого.')}</Txt></View>
        ) : (
          <Composer features={f} busy={uploading} onText={sendText} onAttach={canAttach ? attach : undefined}
            onFile={(kind, uri, name, type, seconds) => upload(kind, uri, name, type, seconds)} />
        )}
      </KeyboardAvoidingView>
      <CallView ref={call} send={sendWs} name={thread?.title ?? ''} avatar={thread?.avatar} turn={thread?.turn ?? null} />
    </SafeAreaView>
  );
}
