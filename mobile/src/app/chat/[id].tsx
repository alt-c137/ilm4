import * as DocumentPicker from 'expo-document-picker';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { usePreventScreenCapture } from 'expo-screen-capture';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, FlatList, KeyboardAvoidingView, Platform, Pressable, View } from 'react-native';
import Animated, { FadeIn, FadeOut, ZoomIn } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, authHeaders, cachedGet, chatFileUrl, wsUrl } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Button, Icon, OfflineBar, Txt } from '@/ui/kit';
import { callsSupported } from '@/lib/webrtc';
import { setOpenThread } from '@/state/calls';
import { CallView, type CallHandle } from '@/ui/call';
import { Composer, type SendOpts } from '@/ui/composer';
import { openSiteUrl } from '@/lib/links';
import { Bubble, DayPill, dayLabel, type Msg } from '@/ui/bubble';
import { fileSize } from '@/ui/media';
import { ChatWallpaper } from '@/ui/wallpaper';
import { PhotoEditor, type EditPhoto } from '@/ui/photo-editor';
import { statusText, type Presence } from '@/lib/presence';
import { BIG, compressVideo, fileSizeOf, uploadInParts, type Stage } from '@/lib/upload';

type Room = { kind: 'group' | 'channel'; title: string; members: number; member: boolean; admin: boolean; muted: boolean;
  can_post: boolean; closed: boolean; verified: boolean };
type CtxCard = { title: string; label: string; price: string; image: string; url: string; closed: boolean; closed_text: string;
  actions: { kind: string; label: string; text: string }[] };
type Thread = { id: number; title: string; subject: string; other_id: number | null; avatar: string; blocked: boolean; nikah: boolean;
  turn: { url: string; username: string; credential: string } | null;
  witnesses: string[]; features: Record<string, any>; card: CtxCard | null; notice: string; warn_text: string;
  room: Room | null; presence?: Presence | null; verified?: boolean };

function NoScreenshots() {
  usePreventScreenCapture('nikah-chat');
  return null;
}

export default function ChatScreen() {
  const { id, answer, call: callNow } = useLocalSearchParams<{ id: string; answer?: string; call?: string }>();
  const { c, t, user, dark, lang } = useApp();
  const [items, setItems] = useState<Msg[]>([]);
  const [down, setDown] = useState(false);          // показать кнопку «вниз» (пролистали вверх)
  const [fresh, setFresh] = useState(0);            // сколько пришло, пока читали старое
  const list = useRef<FlatList<Msg>>(null);
  const scrolledUp = useRef(false);
  const [thread, setThread] = useState<Thread | null>(null);
  const [more, setMore] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<{ stage: Stage; done: number; total: number; name: string } | null>(null);
  const cancelUpload = useRef(false);
  const [editing, setEditing] = useState<EditPhoto | null>(null);
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
    if (scrolledUp.current && m.sender_id !== user?.id) setFresh((n) => n + 1);
    return [...old.filter((x) => x.id !== m.id), norm(m)];
  }), [norm, user?.id]);

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

  // пришли из профиля по кнопке «Звонок» / «Видео» — звоним, как только чат подключился
  const called = useRef(false);
  const threadReady = !!thread;
  useEffect(() => {
    if (!threadReady || called.current || (callNow !== 'audio' && callNow !== 'video')) return;
    called.current = true;
    const timer = setTimeout(() => {
      if (callsSupported) call.current?.start(callNow === 'video');
      else Alert.alert(t('Звонки'), t('Звонки работают в установленном приложении ilm4. В тестовом Expo Go их нет — это ограничение Expo Go.'));
    }, 900);
    return () => clearTimeout(timer);
  }, [threadReady, callNow, t]);

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
        else if (d.type === 'del') setItems((old) => old.filter((m) => !d.ids.includes(m.id)));
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

  // группа / канал: вступить, выйти из «без звука»
  const roomAct = async (action: 'join' | 'mute' | 'unmute') => {
    try {
      await api(`/chat/${id}/room/${action}/`, { body: {} });
      load();
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };

  // долгое нажатие на сообщение: удалить у всех (своё — автор, любое — админ группы или канала)
  const messageMenu = (m: Msg) => {
    if (m.scheduled || m.kind === 'system' || !(m.mine || thread?.room?.admin)) return;
    Alert.alert(t('Сообщение'), undefined, [
      { text: t('Удалить у всех'), style: 'destructive', onPress: async () => {
        try {
          await api(`/chat/msg/${m.id}/delete/`, { body: {} });
          setItems((old) => old.filter((x) => x.id !== m.id));
        } catch (e: any) {
          Alert.alert(e.message);
        }
      } },
      { text: t('Отмена'), style: 'cancel' },
    ]);
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
    cancelUpload.current = false;
    try {
      const show = (stage: Stage, done: number, total: number) => setProgress({ stage, done, total, name });
      let src = uri;
      if (kind === 'video') {
        // как Telegram: сжимаем на телефоне до отправки — быстрее уходит и экономит трафик
        src = await compressVideo(uri, thread?.features.video_height || 720, show);
        if (src !== uri) { name = name.replace(/\.\w+$/, '') + '.mp4'; type = 'video/mp4'; }
      }
      const size = kind === 'file' || kind === 'video' ? fileSizeOf(src) : 0;
      if (size > (thread?.features.file_max_mb || 2000) * 1048576) throw new Error(t('Файл слишком большой'));
      if (size > BIG) {
        add(await uploadInParts(id, kind as 'file' | 'video', src, name, { duration }, show, () => cancelUpload.current));
        return;
      }
      const form = new FormData();
      form.append('kind', kind);
      form.append('duration', String(Math.round(duration)));
      form.append('file', { uri: src, name, type } as any);
      add(await api(`/chat/${id}/upload/`, { form, timeout: 120000 }));
    } catch (e: any) {
      if (e?.code !== 'cancelled') Alert.alert(e.message);
    } finally {
      setUploading(false);
      setProgress(null);
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
      return upload('video', a.uri, a.fileName || 'video.mp4', a.mimeType || 'video/mp4', (a.duration || 0) / 1000);
    }
    // как в Telegram: перед отправкой фото можно порисовать и подписать
    if (Platform.OS !== 'web' && a.width && a.height && !/gif$/i.test(a.mimeType || '')) return setEditing({ uri: a.uri, width: a.width, height: a.height });
    return upload('photo', a.uri, a.fileName || 'photo.jpg', a.mimeType || 'image/jpeg');
  };

  // «файлом» — без сжатия, в исходном качестве (как «Отправить файлом» в Telegram)
  const pickFile = async () => {
    const r = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true, multiple: false });
    if (r.canceled || !r.assets[0]) return;
    const a = r.assets[0];
    const max = (thread?.features.file_max_mb || 2000) * 1048576;
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
  const headBtn = { width: 36, height: 36, borderRadius: 18, backgroundColor: c.accentSoft, alignItems: 'center' as const, justifyContent: 'center' as const };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.card }} edges={['top', 'bottom']}>
      {thread?.nikah && Platform.OS !== 'web' ? <NoScreenshots /> : null}
      <OfflineBar />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 6, paddingRight: 10, paddingVertical: 7, backgroundColor: c.card,
        borderBottomWidth: 0.5, borderBottomColor: c.line }}>
        <Pressable onPress={() => (router.canGoBack() ? router.back() : router.replace('/chats'))} hitSlop={10} style={{ padding: 4 }}>
          <Icon name="chevron-back" size={27} color={c.accent} />
        </Pressable>
        <Pressable disabled={!thread?.room && !thread?.other_id}
          onPress={() => router.push(thread?.room ? `/chat/info/${id}` : `/user/${thread?.other_id}`)}
          style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <Avatar uri={thread?.avatar} name={thread?.title ?? ''} size={40} hue={thread?.other_id ?? Number(id)} />
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
              <Txt style={{ fontSize: 16.5, fontWeight: '700', flexShrink: 1 }} numberOfLines={1}>{thread?.title ?? ''}</Txt>
              {thread?.room?.verified || thread?.verified ? <Icon name="checkmark-circle" size={16} color={c.accent} /> : null}
            </View>
            {thread?.room ? (
              <Txt kind="small" numberOfLines={1}>
                {thread.room.kind === 'channel' ? t('канал · подписчиков: {n}', { n: thread.room.members }) : t('группа · участников: {n}', { n: thread.room.members })}
              </Txt>
            ) : thread?.subject ? <Txt kind="small" numberOfLines={1}>{thread.subject}</Txt> : thread?.presence ? (
              <Txt kind="small" numberOfLines={1} color={thread.presence.online ? c.accent : c.inkSoft}>{statusText(thread.presence, t, lang)}</Txt>
            ) : thread ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                <Icon name="lock-closed" size={11} color={c.ok} />
                <Txt kind="small" numberOfLines={1}>{t('переписка защищена')}</Txt>
              </View>
            ) : null}
          </View>
        </Pressable>
        {f.calls && !thread?.blocked && Platform.OS !== 'web' ? (
          <Pressable hitSlop={6} onPress={() => startCall(false)} style={headBtn}><Icon name="call" size={19} color={c.accent} /></Pressable>
        ) : null}
        {f.video_calls && !thread?.blocked && Platform.OS !== 'web' ? (
          <Pressable hitSlop={6} onPress={() => startCall(true)} style={headBtn}><Icon name="videocam" size={20} color={c.accent} /></Pressable>
        ) : null}
        {thread?.other_id ? (
          <Pressable hitSlop={8} onPress={() => router.push(`/user/${thread.other_id}`)} style={{ padding: 4 }} accessibilityLabel={t('Профиль')}>
            <Icon name="ellipsis-vertical" size={20} color={c.inkSoft} />
          </Pressable>
        ) : null}
        {thread?.room ? (
          <Pressable hitSlop={8} onPress={() => router.push(`/chat/info/${id}`)} style={headBtn}><Icon name="information" size={20} color={c.accent} /></Pressable>
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
        <View style={{ flex: 1 }}>
          {/* фон переписки — настраивается: узор, цвет или своё фото (Профиль → «Фон чата») */}
          <ChatWallpaper />
          <FlatList
            ref={list}
            inverted
            data={data}
            keyExtractor={(m) => String(m.id)}
            onEndReached={older}
            onEndReachedThreshold={0.4}
            initialNumToRender={18} windowSize={11}
            keyboardShouldPersistTaps="handled"
            scrollEventThrottle={120}
            onScroll={(e) => {
              const up = e.nativeEvent.contentOffset.y > 320;
              if (up !== scrolledUp.current) {
                scrolledUp.current = up;
                setDown(up);
                if (!up) setFresh(0);
              }
            }}
            contentContainerStyle={{ paddingHorizontal: 10, paddingTop: 8, paddingBottom: 6 }}
            renderItem={({ item: m, index }) => {
              const older1 = data[index + 1];               // список перевёрнут: следующий по индексу — более старое
              const newer = data[index - 1];
              const newDay = !older1 || older1.day !== m.day;
              const first = newDay || older1.sender_id !== m.sender_id || older1.kind === 'system';
              const last = !newer || newer.day !== m.day || newer.sender_id !== m.sender_id || newer.kind === 'system';
              return (
                <View>
                  {newDay ? <DayPill text={dayLabel(m.day, lang, t)} /> : null}
                  {m.kind === 'system' ? (
                    <View style={{ alignSelf: 'center', marginVertical: 5, maxWidth: '85%', paddingHorizontal: 11, paddingVertical: 4, borderRadius: 12,
                      backgroundColor: dark ? 'rgba(255,255,255,0.12)' : 'rgba(30,28,70,0.28)' }}>
                      <Txt kind="small" color="#fff" style={{ textAlign: 'center', fontWeight: '600' }}>{m.body} · {m.time}</Txt>
                    </View>
                  ) : (
                    <Bubble m={m} first={first} last={last} group={m.room === 'group'} animate={!initial.current?.has(m.id)}
                      onLongPress={messageMenu} onScheduled={scheduledAction} />
                  )}
                  {m.warn && !m.mine && thread?.warn_text ? (
                    <View style={{ alignSelf: 'flex-start', maxWidth: '86%', flexDirection: 'row', gap: 8, marginTop: 6, padding: 10, borderRadius: 14,
                      backgroundColor: '#fff4d6', borderWidth: 1, borderColor: '#f0d58a' }}>
                      <Icon name="shield-outline" size={17} color="#7a5600" />
                      <Txt kind="small" color="#7a5600" style={{ flex: 1, fontWeight: '600' }}>{thread.warn_text}</Txt>
                    </View>
                  ) : null}
                </View>
              );
            }}
          />
          {thread && !data.length ? (
            // пустой диалог: приветствие вместо белого экрана
            <Animated.View entering={FadeIn.duration(250)} pointerEvents="box-none"
              style={{ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, alignItems: 'center', justifyContent: 'center', padding: 24 }}>
              <View style={{ alignItems: 'center', gap: 8, backgroundColor: c.card, borderRadius: 26, paddingVertical: 22, paddingHorizontal: 22, maxWidth: 320 }}>
                <Avatar uri={thread.avatar} name={thread.title} size={72} hue={thread.other_id ?? Number(id)} />
                <Txt kind="h3" style={{ textAlign: 'center' }}>{thread.title}</Txt>
                <Txt kind="small" style={{ textAlign: 'center' }}>
                  {thread.room ? (thread.room.kind === 'channel' ? t('Здесь будут публикации канала.') : t('Напишите первое сообщение в группу.')) : t('Здесь пока пусто. Начните с приветствия.')}
                </Txt>
                {!thread.room && !thread.blocked ? (
                  <Pressable onPress={() => sendText('Ассаляму алейкум!')} style={{ marginTop: 4, backgroundColor: c.accentSoft, borderRadius: 999, paddingHorizontal: 16, paddingVertical: 9 }}>
                    <Txt color={c.accentD} style={{ fontWeight: '700' }}>Ассаляму алейкум! 👋</Txt>
                  </Pressable>
                ) : null}
              </View>
            </Animated.View>
          ) : null}
          {down ? (
            <Animated.View entering={ZoomIn.duration(160)} exiting={FadeOut.duration(120)} style={{ position: 'absolute', right: 12, bottom: 12 }}>
              <Pressable onPress={() => { list.current?.scrollToOffset({ offset: 0, animated: true }); setFresh(0); }}
                accessibilityLabel={t('К последним сообщениям')}
                style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: c.card, alignItems: 'center', justifyContent: 'center',
                  shadowColor: '#000', shadowOpacity: 0.18, shadowRadius: 8, shadowOffset: { width: 0, height: 2 }, elevation: 4 }}>
                <Icon name="chevron-down" size={22} color={c.inkSoft} />
                {fresh ? (
                  <View style={{ position: 'absolute', top: -7, minWidth: 20, paddingHorizontal: 5, height: 20, borderRadius: 10, backgroundColor: c.accent, alignItems: 'center', justifyContent: 'center' }}>
                    <Txt kind="small" color="#fff" style={{ fontSize: 11, fontWeight: '800' }}>{fresh}</Txt>
                  </View>
                ) : null}
              </Pressable>
            </Animated.View>
          ) : null}
        </View>
        {progress ? (
          <View style={{ backgroundColor: c.card, paddingHorizontal: 14, paddingTop: 8, gap: 5 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Txt kind="small" style={{ flex: 1, fontWeight: '700' }} numberOfLines={1}>
                {progress.stage === 'compress' ? t('Отправка…') : progress.name}</Txt>
              {progress.stage === 'upload' ? (
                <Txt kind="small" style={{ fontVariant: ['tabular-nums'] }}>{`${fileSize(progress.done, t)} / ${fileSize(progress.total, t)}`}</Txt>
              ) : null}
              {progress.stage === 'upload' ? (
                <Pressable hitSlop={10} onPress={() => { cancelUpload.current = true; }}><Icon name="close" size={18} color={c.inkSoft} /></Pressable>
              ) : null}
            </View>
            <View style={{ height: 4, borderRadius: 2, backgroundColor: c.line, overflow: 'hidden' }}>
              <View style={{ height: 4, borderRadius: 2, backgroundColor: c.accent, width: `${Math.min(100, (progress.done / Math.max(1, progress.total)) * 100)}%` }} />
            </View>
          </View>
        ) : null}
        {thread?.blocked ? (
          <View style={{ padding: 16, backgroundColor: c.card }}><Txt kind="muted" style={{ textAlign: 'center' }}>{t('Переписка недоступна: один из вас заблокировал другого.')}</Txt></View>
        ) : thread?.room && !thread.room.can_post ? (
          <View style={{ padding: 10, backgroundColor: c.card, borderTopWidth: 0.5, borderTopColor: c.line }}>
            {thread.room.closed ? <Txt kind="muted" style={{ textAlign: 'center' }}>{t('Чат закрыт модератором.')}</Txt>
              : !thread.room.member ? <Button title={thread.room.kind === 'channel' ? t('Подписаться') : t('Вступить в группу')} onPress={() => roomAct('join')} />
                : <Button kind="ghost" title={thread.room.muted ? t('Включить звук') : t('Без звука')} onPress={() => roomAct(thread.room?.muted ? 'unmute' : 'mute')} />}
          </View>
        ) : (
          <Composer features={f} busy={uploading} onText={sendText} onAttach={canAttach ? attach : undefined}
            onFile={(kind, uri, name, type, seconds) => upload(kind, uri, name, type, seconds)} />
        )}
      </KeyboardAvoidingView>
      <PhotoEditor photo={editing} onDone={(uri) => { setEditing(null); if (uri) upload('photo', uri, 'photo.jpg', 'image/jpeg'); }} />
      <CallView ref={call} send={sendWs} name={thread?.title ?? ''} avatar={thread?.avatar} turn={thread?.turn ?? null} />
    </SafeAreaView>
  );
}
