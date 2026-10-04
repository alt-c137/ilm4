/**
 * Переписка — по механике Telegram: ответ (свайп влево или меню), правка своего сообщения, реакции,
 * закреплённые сообщения под шапкой, пересылка, «удалить у себя / у всех», поиск по чату, «печатает…»,
 * черновик, переход к сообщению, комментарии под постами канала.
 */
/* eslint-disable react-hooks/refs, react-hooks/purity -- меню сообщения создаёт обработчики при отрисовке, а вызываются они по нажатию;
   React Compiler считает это чтением ref во время отрисовки. */
import * as Clipboard from 'expo-clipboard';
import * as DocumentPicker from 'expo-document-picker';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { usePreventScreenCapture } from 'expo-screen-capture';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, FlatList, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import Animated, { FadeIn, FadeInUp, FadeOut, ZoomIn } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, authHeaders, cachedGet, chatFileUrl, wsUrl } from '@/lib/api';
import { useApp } from '@/state/app';
import { AdCard, Avatar, Button, Icon, OfflineBar, Sheet, Txt, type AdData, type SheetItem } from '@/ui/kit';
import { callsSupported } from '@/lib/webrtc';
import { setOpenThread } from '@/state/calls';
import { CallView, type CallHandle } from '@/ui/call';
import { Composer, type Banner, type ComposerHandle, type SendOpts } from '@/ui/composer';
import { openSiteUrl } from '@/lib/links';
import { Bubble, DayPill, dayLabel, type Fwd, type Msg } from '@/ui/bubble';
import { fileSize } from '@/ui/media';
import { ChatWallpaper } from '@/ui/wallpaper';
import { PhotoEditor, type EditPhoto } from '@/ui/photo-editor';
import { PhotoViewer } from '@/ui/photo-viewer';
import { statusText, type Presence } from '@/lib/presence';
import { BIG, compressVideo, fileSizeOf, uploadInParts, type Stage } from '@/lib/upload';

type Room = { kind: 'group' | 'channel'; title: string; members: number; member: boolean; admin: boolean; muted: boolean;
  can_post: boolean; closed: boolean; verified: boolean };
type CtxCard = { title: string; label: string; price: string; image: string; url: string; closed: boolean; closed_text: string;
  actions: { kind: string; label: string; text: string }[] };
type Thread = { id: number; title: string; subject: string; other_id: number | null; avatar: string; blocked: boolean; nikah: boolean;
  turn: { url: string; username: string; credential: string } | null;
  witnesses: string[]; features: Record<string, any>; card: CtxCard | null; notice: string; warn_text: string;
  room: Room | null; presence?: Presence | null; verified?: boolean;
  saved?: boolean; muted?: boolean; pins?: Msg[]; draft?: string; can_pin?: boolean; member?: boolean; protected?: boolean;
  reactions?: string[]; comments?: boolean; edit_hours?: number; support?: '' | 'call' | 'drop' };
type Typer = { name: string; what: string };
type Found = { id: number; name: string; text: string };

function NoScreenshots() {
  usePreventScreenCapture('nikah-chat');
  return null;
}

/** Текст без знаков оформления — для полоски ответа и закрепа. */
function plain(m: Msg, t: (s: string) => string) {
  if (m.body) return m.body.replace(/\|\|\S[\s\S]*?\|\|/g, '▒▒▒').replace(/\*\*|__|~~|`/g, '');
  return ({ photo: t('Фото'), video: t('Видео'), voice: t('Голосовое сообщение'), circle: t('Видеосообщение'), file: m.file_name || t('Файл') } as Record<string, string>)[m.kind] ?? '';
}

export default function ChatScreen() {
  const { id, answer, call: callNow, at } = useLocalSearchParams<{ id: string; answer?: string; call?: string; at?: string }>();
  const { c, t, user, dark, lang } = useApp();
  const [items, setItems] = useState<Msg[]>([]);
  const [down, setDown] = useState(false);          // показать кнопку «вниз» (пролистали вверх)
  const [fresh, setFresh] = useState(0);            // сколько пришло, пока читали старое
  const list = useRef<FlatList<Msg>>(null);
  const scrolledUp = useRef(false);
  const [thread, setThread] = useState<Thread | null>(null);
  const [ad, setAd] = useState<AdData | null>(null);        // реклама — только в открытых каналах, внизу ленты
  const [more, setMore] = useState(false);
  const [moreAfter, setMoreAfter] = useState(false);     // открыто «окно» в прошлом — ниже есть ещё сообщения
  const windowed = useRef(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<{ stage: Stage; done: number; total: number; name: string } | null>(null);
  const cancelUpload = useRef(false);
  const [editing, setEditing] = useState<EditPhoto | null>(null);
  const call = useRef<CallHandle>(null);
  const ws = useRef<WebSocket | null>(null);
  const initial = useRef<Set<number> | null>(null);   // загруженные сразу — без анимации появления
  const composer = useRef<ComposerHandle>(null);
  const [reply, setReply] = useState<Msg | null>(null);
  const [edit, setEdit] = useState<Msg | null>(null);
  const replyRef = useRef<Msg | null>(null);
  const editRef = useRef<Msg | null>(null);
  const [menu, setMenu] = useState<Msg | null>(null);
  const [chatMenu, setChatMenu] = useState(false);
  const [pins, setPins] = useState<Msg[]>([]);
  const [pinAt, setPinAt] = useState(0);
  const [typers, setTypers] = useState<Record<number, Typer>>({});
  const typerTimers = useRef<Record<number, ReturnType<typeof setTimeout>>>({});
  const typingSent = useRef(0);
  const [flash, setFlash] = useState<number | null>(null);
  const [viewerId, setViewerId] = useState<number | null>(null);
  const [search, setSearch] = useState(false);
  const [query, setQuery] = useState('');
  const [found, setFound] = useState<Found[] | null>(null);
  const [foundAt, setFoundAt] = useState(0);
  const pendingJump = useRef<number | null>(null);
  const draftTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const draftSeeded = useRef(false);

  const norm = useCallback((m: Msg): Msg => ({
    ...m, mine: m.sender_id === user?.id, url: ['photo', 'video', 'voice', 'circle', 'file'].includes(m.kind) ? chatFileUrl(m.id) : '',
  }), [user?.id]);

  // новое сообщение; запланированное, которое ушло, — заменяем и переносим в конец
  const add = useCallback((m: Msg) => {
    if (m.comment_of) {            // комментарий к посту канала: в ленту не идёт — только счётчик у поста
      setItems((old) => old.map((x) => (x.id === m.comment_of ? { ...x, comments: (x.comments ?? 0) + 1 } : x)));
      return;
    }
    setTypers((old) => { if (!old[m.sender_id]) return old; const next = { ...old }; delete next[m.sender_id]; return next; });
    if (windowed.current && m.sender_id !== user?.id) { setFresh((n) => n + 1); return; }     // читают старое — не подмешиваем
    setItems((old) => {
      const prev = old.find((x) => x.id === m.id);
      if (prev && !(prev.scheduled && !m.scheduled)) return old;
      if (scrolledUp.current && m.sender_id !== user?.id) setFresh((n) => n + 1);
      return [...old.filter((x) => x.id !== m.id), norm(m)];
    });
  }, [norm, user?.id]);

  const apply = useCallback((data: { items: Msg[]; thread?: Thread; more: boolean; more_after?: boolean; ad?: AdData | null }) => {
    if (!initial.current) initial.current = new Set(data.items.map((m: Msg) => m.id));
    if (data.ad !== undefined) setAd(data.ad);
    setItems(data.items.map(norm));
    setMore(data.more);
    setMoreAfter(!!data.more_after);
    windowed.current = !!data.more_after;
    if (data.thread) {
      setThread(data.thread);
      setPins((data.thread.pins ?? []).map(norm));
      setPinAt(Math.max(0, (data.thread.pins ?? []).length - 1));
      if (!draftSeeded.current) {            // черновик подставляем один раз — при открытии чата
        draftSeeded.current = true;
        if (data.thread.draft) composer.current?.setText(data.thread.draft);
      }
    }
  }, [norm]);

  const load = useCallback(async () => {
    if (windowed.current) return;            // открыто «окно» вокруг старого сообщения — не перезаписываем
    try {
      const { data } = await cachedGet(`/chat/${id}/`);
      apply(data);
    } catch (e: any) {
      Alert.alert(e.message);
    }
  }, [id, apply]);

  // сообщение далеко в прошлом: загружаем «окно» вокруг него и после отрисовки прокручиваем к нему
  const jumpFar = useCallback(async (mid: number) => {
    try {
      const data = await api(`/chat/${id}/?around=${mid}`);
      pendingJump.current = mid;
      apply(data);
    } catch (e: any) {
      Alert.alert(e.message);
    }
  }, [id, apply]);

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

  const patch = useCallback((mid: number, part: Partial<Msg>) => {
    setItems((old) => old.map((m) => (m.id === mid ? { ...m, ...part } : m)));
    setPins((old) => old.map((m) => (m.id === mid ? { ...m, ...part } : m)));
  }, []);

  const onTyping = useCallback((d: { user_id: number; name: string; what: string }) => {
    clearTimeout(typerTimers.current[d.user_id]);
    setTypers((old) => ({ ...old, [d.user_id]: { name: d.name, what: d.what } }));
    typerTimers.current[d.user_id] = setTimeout(() => {
      setTypers((old) => { const next = { ...old }; delete next[d.user_id]; return next; });
    }, 5500);
  }, []);

  const onPin = useCallback((d: { id: number; on: boolean; msg: Msg }) => {
    setItems((old) => old.map((m) => (m.id === d.id ? { ...m, pinned: d.on } : m)));
    setPins((old) => {
      const rest = old.filter((m) => m.id !== d.id);
      const next = d.on ? [...rest, norm(d.msg)].sort((a, b) => a.id - b.id) : rest;
      setPinAt(Math.max(0, next.length - 1));
      return next;
    });
  }, [norm]);

  // живые сообщения: тот же WebSocket, что у сайта; обрыв — переподключение
  useEffect(() => {
    windowed.current = false;
    draftSeeded.current = false;
    // первая загрузка переписки; открыли чат сразу на нужном сообщении (из поиска, уведомления) — «окно» вокруг него
    // eslint-disable-next-line react-hooks/set-state-in-effect -- загрузка данных при открытии чата
    if (at && /^\d+$/.test(at)) jumpFar(Number(at)); else load();
    let stop = false;
    let retry: ReturnType<typeof setTimeout>;
    const timers = typerTimers.current;
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
        else if (d.type === 'read') setItems((old) => old.map((m) => (d.ids.includes(m.id) || (d.until && m.iso && Date.parse(m.iso) / 1000 <= d.until) ? { ...m, read: true } : m)));
        else if (d.type === 'del') {
          setItems((old) => old.filter((m) => !d.ids.includes(m.id)));
          setPins((old) => old.filter((m) => !d.ids.includes(m.id)));
        } else if (d.type === 'edit') patch(d.id, { body: d.body, edited: d.edited });
        else if (d.type === 'pin') onPin(d);
        else if (d.type === 'reaction') {
          setItems((old) => old.map((m) => (m.id === d.id
            ? { ...m, reactions: d.reactions, my_reaction: d.user_id === user?.id ? d.emoji : m.my_reaction } : m)));
        } else if (d.type === 'typing') onTyping(d);
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
      Object.values(timers).forEach(clearTimeout);
      ws.current?.close();
    };
  }, [id, load, add, patch, onPin, onTyping, user?.id, at, jumpFar]);

  // ушли с экрана — сохранить недописанное как черновик
  useFocusEffect(useCallback(() => () => {
    if (draftTimer.current) clearTimeout(draftTimer.current);
    const text = editRef.current ? '' : (composer.current?.getText() ?? '').trim();
    api(`/chat/${id}/draft/`, { body: { text } }).catch(() => {});
  }, [id]));

  const older = async () => {
    if (!more || !items.length) return;
    const r = await api(`/chat/${id}/?before=${items[0].id}`).catch(() => null);
    if (r) {
      setItems((old) => [...r.items.map(norm), ...old.filter((x) => !r.items.some((y: Msg) => y.id === x.id))]);
      setMore(r.more);
    }
  };
  const newer = async () => {
    if (!moreAfter || !items.length) return;
    const r = await api(`/chat/${id}/?after=${items[items.length - 1].id}`).catch(() => null);
    if (r) {
      setItems((old) => [...old, ...r.items.map(norm).filter((x: Msg) => !old.some((y) => y.id === x.id))]);
      setMoreAfter(!!r.more_after);
      windowed.current = !!r.more_after;
    }
  };

  // ---------- переход к сообщению (ответ, закреп, найденное) ----------
  const scrollTo = (mid: number, list_: Msg[]) => {
    const index = [...list_].reverse().findIndex((m) => m.id === mid);
    if (index < 0) return false;
    list.current?.scrollToIndex({ index, viewPosition: 0.5, animated: true });
    setFlash(mid);
    setTimeout(() => setFlash((f) => (f === mid ? null : f)), 1500);
    return true;
  };
  const jump = (mid: number) => {
    if (!scrollTo(mid, items)) jumpFar(mid);
  };
  useEffect(() => {
    const mid = pendingJump.current;
    if (!mid || !items.some((m) => m.id === mid)) return;
    pendingJump.current = null;
    const timer = setTimeout(() => scrollTo(mid, items), 250);
    return () => clearTimeout(timer);
  }, [items]);
  const toLatest = async () => {
    setFresh(0);
    if (windowed.current) {
      windowed.current = false;
      await load();
    }
    list.current?.scrollToOffset({ offset: 0, animated: true });
  };

  // ---------- ответ и правка ----------
  const startReply = useCallback((m: Msg) => {
    if (editRef.current) composer.current?.setText('');
    editRef.current = null; setEdit(null);
    replyRef.current = m; setReply(m);
    composer.current?.focus();
  }, []);
  const startEdit = async (m: Msg) => {
    replyRef.current = null; setReply(null);
    editRef.current = m; setEdit(m);
    composer.current?.setText(m.body);
    composer.current?.focus();
    try {                 // исходный текст со знаками оформления
      const r = await api<{ body: string }>(`/chat/msg/${m.id}/raw/`, { body: {} });
      if (editRef.current?.id === m.id) composer.current?.setText(r.body);
    } catch { /* останется текст из ленты */ }
  };
  const closeBanner = () => {
    if (editRef.current) composer.current?.setText('');
    replyRef.current = null; editRef.current = null;
    setReply(null); setEdit(null);
  };

  const sendText = async (body: string, opts: SendOpts = {}) => {
    try {
      const ed = editRef.current;
      if (ed) {
        const r = await api<Msg>(`/chat/msg/${ed.id}/edit/`, { body: { body } });
        patch(ed.id, { body: r.body, edited: r.edited });
        editRef.current = null; setEdit(null);
        return true;
      }
      const rp = replyRef.current;
      const extra = rp ? { reply_to: rp.id } : {};
      if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify({ body, ...opts, ...extra }));
      else add(await api(`/chat/${id}/send/`, { body: { body, ...opts, ...extra } }));
      replyRef.current = null; setReply(null);
      if (opts.schedule) Alert.alert(t('Сообщение запланировано'));
      if (windowed.current) toLatest();
      return true;
    } catch (e: any) {
      Alert.alert(e.message);
      return false;
    }
  };

  // черновик и «печатает…»
  const onChangeText = useCallback((text: string) => {
    if (editRef.current) return;
    if (draftTimer.current) clearTimeout(draftTimer.current);
    draftTimer.current = setTimeout(() => { api(`/chat/${id}/draft/`, { body: { text: text.trim() } }).catch(() => {}); }, 1500);
  }, [id]);
  const sayTyping = useCallback((what: 'text' | 'voice' | 'circle') => {
    const now = Date.now();
    if (what === 'text' && now - typingSent.current < 4000) return;
    typingSent.current = now;
    sendWs({ type: 'typing', what });
  }, [sendWs]);

  // группа / канал: вступить, выйти из «без звука»
  const roomAct = async (action: 'join' | 'mute' | 'unmute') => {
    try {
      await api(`/chat/${id}/room/${action}/`, { body: {} });
      load();
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };

  // ---------- действия с сообщением ----------
  const react = useCallback(async (m: Msg, emoji: string) => {
    try {
      const r = await api<{ reactions: Msg['reactions']; my_reaction: string }>(`/chat/msg/${m.id}/react/`, { body: { emoji } });
      setItems((old) => old.map((x) => (x.id === m.id ? { ...x, reactions: r.reactions, my_reaction: r.my_reaction } : x)));
    } catch (e: any) {
      Alert.alert(e.message);
    }
  }, []);
  const msgAct = async (m: Msg, action: 'pin' | 'unpin' | 'hide' | 'delete') => {
    try {
      await api(`/chat/msg/${m.id}/${action}/`, { body: {} });
      if (action === 'hide' || action === 'delete') {
        setItems((old) => old.filter((x) => x.id !== m.id));
        setPins((old) => old.filter((x) => x.id !== m.id));
      } else if (Platform.OS === 'web') onPin({ id: m.id, on: action === 'pin', msg: { ...m, pinned: action === 'pin' } });
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };
  const save = async (m: Msg) => {
    try {
      await api('/chat/forward/', { body: { ids: [m.id], to: ['saved'] } });
      Alert.alert(t('Сохранено в «Избранное»'));
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };
  const openMenu = useCallback((m: Msg) => { if (m.kind !== 'system') setMenu(m); }, []);
  const canWrite = !thread?.blocked && (!thread?.room || thread.room.can_post);
  const menuItems = (m: Msg): SheetItem[] => {
    const age = m.iso ? (Date.now() - new Date(m.iso).getTime()) / 3600e3 : 0;
    const canEdit = !!m.mine && m.kind !== 'voice' && m.kind !== 'circle' && (m.scheduled || !thread?.edit_hours || age < thread.edit_hours);
    const free = !thread?.protected;
    if (m.scheduled) return canEdit ? [{ icon: 'pencil-outline', title: t('Изменить'), onPress: () => startEdit(m) }] : [];
    return [
      ...(canWrite ? [{ icon: 'arrow-undo-outline' as const, title: t('Ответить'), onPress: () => startReply(m) }] : []),
      ...(canEdit ? [{ icon: 'pencil-outline' as const, title: t('Изменить'), onPress: () => startEdit(m) }] : []),
      ...(m.body && free ? [{ icon: 'copy-outline' as const, title: t('Копировать текст'), onPress: () => { Clipboard.setStringAsync(m.body); } }] : []),
      ...(free ? [{ icon: 'arrow-redo-outline' as const, title: t('Переслать'), onPress: () => router.push({ pathname: '/chat/forward', params: { ids: String(m.id) } }) }] : []),
      ...(free && !thread?.saved ? [{ icon: 'bookmark-outline' as const, title: t('В избранное'), onPress: () => save(m) }] : []),
      ...(thread?.can_pin ? [{ icon: 'pin-outline' as const, title: m.pinned ? t('Открепить') : t('Закрепить'), onPress: () => msgAct(m, m.pinned ? 'unpin' : 'pin') }] : []),
      { icon: 'trash-outline' as const, title: t('Удалить у себя'), onPress: () => msgAct(m, 'hide') },
      ...(m.mine || thread?.room?.admin ? [{ icon: 'trash' as const, danger: true, title: t('Удалить у всех'), onPress: () => Alert.alert(t('Удалить сообщение у всех?'), undefined, [
        { text: t('Отмена'), style: 'cancel' as const }, { text: t('Удалить'), style: 'destructive' as const, onPress: () => msgAct(m, 'delete') }]) }] : []),
    ];
  };

  const scheduledAction = useCallback(async (m: Msg, action: 'send' | 'cancel') => {
    try {
      const r = await api(`/chat/msg/${m.id}/${action}/`, { body: {} });
      if (action === 'cancel') setItems((old) => old.filter((x) => x.id !== m.id));
      else add(r);
    } catch (e: any) {
      Alert.alert(e.message);
    }
  }, [add]);

  const upload = async (kind: string, uri: string, name: string, type: string, duration = 0) => {
    setUploading(true);
    cancelUpload.current = false;
    const rp = replyRef.current;
    replyRef.current = null; setReply(null);
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
        add(await uploadInParts(id, kind as 'file' | 'video', src, name, { duration, reply_to: rp?.id }, show, () => cancelUpload.current));
        return;
      }
      const form = new FormData();
      form.append('kind', kind);
      form.append('duration', String(Math.round(duration)));
      if (rp) form.append('reply_to', String(rp.id));
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

  const [attachOpen, setAttachOpen] = useState(false);
  const f = thread?.features ?? {};
  const canAttach = !!(f.photo || f.video || f.file);
  const data = [...items].reverse();
  const photos = items.filter((m) => m.kind === 'photo');
  const viewer = viewerId === null ? null : Math.max(0, photos.findIndex((m) => m.id === viewerId));
  const headBtn = { width: 36, height: 36, borderRadius: 18, backgroundColor: c.accentSoft, alignItems: 'center' as const, justifyContent: 'center' as const };

  // ---------- поиск по чату ----------
  const runSearch = async () => {
    const q = query.trim();
    if (q.length < 2) return setFound(null);
    try {
      const r = await api<{ items: Found[] }>(`/chat/${id}/search/?q=${encodeURIComponent(q)}`);
      setFound(r.items);
      setFoundAt(0);
      if (r.items[0]) jump(r.items[0].id);
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };
  const stepFound = (by: number) => {
    if (!found?.length) return;
    const next = (foundAt + by + found.length) % found.length;
    setFoundAt(next);
    jump(found[next].id);
  };

  // ---------- шапка: статус или «печатает…» ----------
  const who = Object.values(typers);
  const typingText = who.length
    ? `${thread?.room ? who.slice(0, 2).map((x) => x.name).join(', ') + ' ' : ''}${who[0].what === 'voice' ? t('записывает голосовое') : who[0].what === 'circle' ? t('записывает кружок') : t('печатает')}…`
    : '';
  const stateAct = async (action: 'mute' | 'unmute' | 'clear' | 'hide' | 'support_call' | 'support_drop') => {
    try {
      await api(`/chat/${id}/state/${action}/`, { body: {} });
      if (action === 'support_call' || action === 'support_drop') return setThread((th) => (th ? { ...th, support: action === 'support_call' ? 'drop' : 'call' } : th));
      if (action === 'hide') return router.canGoBack() ? router.back() : router.replace('/chats');
      if (action === 'clear') { setItems([]); setPins([]); }
      setThread((th) => (th ? { ...th, muted: action === 'mute' ? true : action === 'unmute' ? false : th.muted } : th));
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };
  const openFwd = useCallback((fw: Fwd) => {
    if (fw.user) router.push(`/user/${fw.user}`);
    else if (fw.room) router.push(`/chat/${fw.room}`);
  }, []);
  const openPhoto = useCallback((m: Msg) => setViewerId(m.id), []);
  const openComments = useCallback((m: Msg) => router.push({ pathname: '/chat/post/[id]', params: { id: String(m.id), thread: String(id) } }), [id]);
  const pin = pins[Math.min(pinAt, pins.length - 1)];
  const banner: Banner | null = edit ? { kind: 'edit', title: t('Изменение сообщения'), text: plain(edit, t) }
    : reply ? { kind: 'reply', title: reply.sender_name, text: plain(reply, t) } : null;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.card }} edges={['top', 'bottom']}>
      {thread?.nikah && Platform.OS !== 'web' ? <NoScreenshots /> : null}
      <OfflineBar />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 6, paddingRight: 6, paddingVertical: 7, backgroundColor: c.card,
        borderBottomWidth: 0.5, borderBottomColor: c.line }}>
        <Pressable onPress={() => (router.canGoBack() ? router.back() : router.replace('/chats'))} hitSlop={10} style={{ padding: 4 }}>
          <Icon name="chevron-back" size={27} color={c.accent} />
        </Pressable>
        <Pressable disabled={!thread?.room && !thread?.other_id}
          onPress={() => router.push(thread?.room ? `/chat/info/${id}` : `/user/${thread?.other_id}`)}
          style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          {thread?.saved ? (
            <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: '#5b76f7', alignItems: 'center', justifyContent: 'center' }}><Icon name="bookmark" size={19} color="#fff" /></View>
          ) : <Avatar uri={thread?.avatar} name={thread?.title ?? ''} size={40} hue={thread?.other_id ?? Number(id)} />}
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
              <Txt style={{ fontSize: 16.5, fontWeight: '700', flexShrink: 1 }} numberOfLines={1}>{thread?.title ?? ''}</Txt>
              {thread?.room?.verified || thread?.verified ? <Icon name="checkmark-circle" size={16} color={c.accent} /> : null}
              {thread?.muted ? <Icon name="notifications-off" size={13} color={c.inkSoft} /> : null}
            </View>
            {typingText ? <Txt kind="small" numberOfLines={1} color={c.accent} style={{ fontWeight: '600' }}>{typingText}</Txt>
              : thread?.saved ? <Txt kind="small" numberOfLines={1}>{t('заметки и пересланное — видите только вы')}</Txt>
                : thread?.room ? (
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
        <Pressable hitSlop={8} onPress={() => setChatMenu(true)} style={{ padding: 6 }} accessibilityLabel={t('Ещё')}>
          <Icon name="ellipsis-vertical" size={21} color={c.inkSoft} />
        </Pressable>
      </View>

      {search ? (
        <Animated.View entering={FadeInUp.duration(160)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 12, paddingRight: 6, paddingVertical: 5, backgroundColor: c.card,
          borderBottomWidth: 0.5, borderBottomColor: c.line }}>
          <Icon name="search" size={18} color={c.inkSoft} />
          <TextInput value={query} onChangeText={setQuery} onSubmitEditing={runSearch} autoFocus returnKeyType="search" placeholder={t('Поиск по этому чату')}
            placeholderTextColor={c.inkSoft} style={{ flex: 1, height: 38, fontSize: 15.5, color: c.ink, paddingVertical: 0 }} />
          <Txt kind="small" style={{ fontVariant: ['tabular-nums'] }}>{found ? (found.length ? `${foundAt + 1} / ${found.length}` : t('не найдено')) : ''}</Txt>
          <Pressable onPress={() => stepFound(1)} hitSlop={6} style={{ padding: 7 }}><Icon name="chevron-up" size={20} color={c.inkSoft} /></Pressable>
          <Pressable onPress={() => stepFound(-1)} hitSlop={6} style={{ padding: 7 }}><Icon name="chevron-down" size={20} color={c.inkSoft} /></Pressable>
          <Pressable onPress={() => { setSearch(false); setQuery(''); setFound(null); }} hitSlop={6} style={{ padding: 7 }}><Icon name="close" size={20} color={c.inkSoft} /></Pressable>
        </Animated.View>
      ) : null}
      {pin ? (
        // закреплённое сообщение: нажатие — перейти к нему; следующее нажатие — к предыдущему закрепу
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingLeft: 12, paddingRight: 4, paddingVertical: 6, backgroundColor: c.card,
          borderBottomWidth: 0.5, borderBottomColor: c.line }}>
          <Pressable onPress={() => { jump(pin.id); setPinAt(pinAt > 0 ? pinAt - 1 : pins.length - 1); }} style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <View style={{ width: 3, height: 34, borderRadius: 2, backgroundColor: c.accent }} />
            <View style={{ flex: 1 }}>
              <Txt kind="small" color={c.accent} style={{ fontWeight: '800' }} numberOfLines={1}>
                {t('Закреплённое сообщение')}{pins.length > 1 ? ` · ${Math.min(pinAt, pins.length - 1) + 1}/${pins.length}` : ''}</Txt>
              <Txt kind="small" style={{ fontSize: 14 }} numberOfLines={1}>{plain(pin, t)}</Txt>
            </View>
          </Pressable>
          {thread?.can_pin ? (
            <Pressable hitSlop={8} onPress={() => Alert.alert(t('Открепить сообщение?'), undefined, [
              { text: t('Отмена'), style: 'cancel' }, { text: t('Открепить'), onPress: () => msgAct(pin, 'unpin') }])} style={{ padding: 8 }}>
              <Icon name="close" size={19} color={c.inkSoft} />
            </Pressable>
          ) : null}
        </View>
      ) : null}
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
            ListHeaderComponent={ad ? <AdCard ad={ad} onOpen={openSiteUrl} style={{ borderRadius: 18, marginHorizontal: 12, marginVertical: 8 }} /> : null}
            keyExtractor={(m) => String(m.id)}
            onEndReached={older}
            onEndReachedThreshold={0.4}
            onStartReached={newer}
            onStartReachedThreshold={0.2}
            onScrollToIndexFailed={(info) => {
              list.current?.scrollToOffset({ offset: info.averageItemLength * info.index, animated: false });
              setTimeout(() => list.current?.scrollToIndex({ index: info.index, viewPosition: 0.5, animated: true }), 250);
            }}
            initialNumToRender={18} windowSize={11}
            keyboardShouldPersistTaps="handled"
            scrollEventThrottle={120}
            onScroll={(e) => {
              const up = e.nativeEvent.contentOffset.y > 320;
              if (up !== scrolledUp.current) {
                scrolledUp.current = up;
                setDown(up);
                if (!up && !windowed.current) setFresh(0);
              }
            }}
            contentContainerStyle={{ paddingHorizontal: 10, paddingTop: 8, paddingBottom: 6 }}
            renderItem={({ item: m, index }) => {
              const older1 = data[index + 1];               // список перевёрнут: следующий по индексу — более старое
              const newer1 = data[index - 1];
              const newDay = !older1 || older1.day !== m.day;
              const first = newDay || older1.sender_id !== m.sender_id || older1.kind === 'system';
              const last = !newer1 || newer1.day !== m.day || newer1.sender_id !== m.sender_id || newer1.kind === 'system';
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
                      flash={flash === m.id} comments={!!thread?.comments && m.room === 'channel'} canReply={canWrite}
                      onLongPress={openMenu} onScheduled={scheduledAction} onReply={startReply} onGoto={jump} onReact={react}
                      onPhoto={openPhoto} onFwd={openFwd} onComments={openComments} />
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
                {thread.saved ? <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: '#5b76f7', alignItems: 'center', justifyContent: 'center' }}><Icon name="bookmark" size={32} color="#fff" /></View>
                  : <Avatar uri={thread.avatar} name={thread.title} size={72} hue={thread.other_id ?? Number(id)} />}
                <Txt kind="h3" style={{ textAlign: 'center' }}>{thread.title}</Txt>
                <Txt kind="small" style={{ textAlign: 'center' }}>
                  {thread.saved ? t('Пересылайте сюда сообщения, пишите заметки, храните файлы. Видите это только вы.')
                    : thread.room ? (thread.room.kind === 'channel' ? t('Здесь будут публикации канала.') : t('Напишите первое сообщение в группу.')) : t('Здесь пока пусто. Начните с приветствия.')}
                </Txt>
                {!thread.room && !thread.blocked && !thread.saved ? (
                  <Pressable onPress={() => sendText('Ассаляму алейкум!')} style={{ marginTop: 4, backgroundColor: c.accentSoft, borderRadius: 999, paddingHorizontal: 16, paddingVertical: 9 }}>
                    <Txt color={c.accentD} style={{ fontWeight: '700' }}>Ассаляму алейкум!</Txt>
                  </Pressable>
                ) : null}
              </View>
            </Animated.View>
          ) : null}
          {down || moreAfter ? (
            <Animated.View entering={ZoomIn.duration(160)} exiting={FadeOut.duration(120)} style={{ position: 'absolute', right: 12, bottom: 12 }}>
              <Pressable onPress={toLatest} accessibilityLabel={t('К последним сообщениям')}
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
          <Composer ref={composer} features={f} busy={uploading} onText={sendText} onAttach={canAttach ? () => setAttachOpen(true) : undefined}
            banner={banner} onBannerClose={closeBanner} onChange={onChangeText} onTyping={sayTyping}
            onFile={(kind, uri, name, type, seconds) => upload(kind, uri, name, type, seconds)} />
        )}
      </KeyboardAvoidingView>

      {/* меню сообщения: сверху реакции, ниже действия */}
      <Sheet open={!!menu} onClose={() => setMenu(null)} items={menu ? menuItems(menu) : []}
        header={menu && !menu.scheduled && thread?.reactions?.length && thread.member !== false ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} keyboardShouldPersistTaps="handled"
            contentContainerStyle={{ paddingHorizontal: 14, paddingBottom: 8, gap: 2 }}>
            {thread.reactions.map((e) => (
              <Pressable key={e} onPress={() => { const m = menu; setMenu(null); react(m, e); }}
                style={{ width: 46, height: 46, borderRadius: 23, alignItems: 'center', justifyContent: 'center', backgroundColor: menu.my_reaction === e ? c.accentSoft : 'transparent' }}>
                <Text style={{ fontSize: 26 }}>{e}</Text>
              </Pressable>
            ))}
          </ScrollView>
        ) : undefined} />
      <Sheet open={chatMenu} onClose={() => setChatMenu(false)} items={[
        { icon: 'search-outline', title: t('Поиск'), onPress: () => setSearch(true) },
        ...(thread?.room ? [{ icon: 'information-circle-outline' as const, title: t('Сведения и участники'), onPress: () => router.push(`/chat/info/${id}`) }]
          : thread?.other_id ? [{ icon: 'person-outline' as const, title: t('Профиль'), onPress: () => router.push(`/user/${thread.other_id}`) }] : []),
        ...(f.video_calls && !thread?.blocked && Platform.OS !== 'web' ? [{ icon: 'videocam-outline' as const, title: t('Видеозвонок'), onPress: () => startCall(true) }] : []),
        ...(!thread?.saved ? [{ icon: thread?.muted ? 'notifications-outline' as const : 'notifications-off-outline' as const,
          title: thread?.muted ? t('Включить звук') : t('Без звука'), onPress: () => stateAct(thread?.muted ? 'unmute' : 'mute') }] : []),
        ...(thread?.support === 'call' ? [{ icon: 'shield-checkmark-outline' as const, title: t('Позвать поддержку'), subtitle: t('Она увидит сообщения, написанные после этого'),
          onPress: () => Alert.alert(t('Позвать поддержку ilm4 в этот чат?'), t('Она увидит сообщения, написанные после этого.'), [
            { text: t('Отмена'), style: 'cancel' }, { text: t('Позвать'), onPress: () => stateAct('support_call') }]) }] : []),
        ...(thread?.support === 'drop' ? [{ icon: 'shield-outline' as const, title: t('Отключить поддержку'), onPress: () => stateAct('support_drop') }] : []),
        { icon: 'image-outline', title: t('Фон чата'), onPress: () => router.push('/chat-look') },
        ...(!thread?.room || thread.room.member ? [{ icon: 'brush-outline' as const, title: t('Очистить историю'), subtitle: t('Сообщения пропадут только у вас'),
          onPress: () => Alert.alert(t('Очистить историю?'), t('Сообщения пропадут только у вас.'), [
            { text: t('Отмена'), style: 'cancel' as const }, { text: t('Очистить'), style: 'destructive' as const, onPress: () => stateAct('clear') }]) }] : []),
        ...(!thread?.room && !thread?.saved ? [{ icon: 'trash-outline' as const, danger: true, title: t('Удалить чат'),
          onPress: () => Alert.alert(t('Удалить чат?'), t('Он пропадёт из вашего списка; у собеседника переписка останется.'), [
            { text: t('Отмена'), style: 'cancel' as const }, { text: t('Удалить'), style: 'destructive' as const, onPress: () => stateAct('hide') }]) }] : []),
      ]} />
      <Sheet open={attachOpen} onClose={() => setAttachOpen(false)} title={t('Отправить')} items={[
        ...(f.photo || f.video ? [
          { icon: 'images-outline' as const, title: t('Из галереи'), subtitle: t('Фото и видео сжимаются: быстрее отправка'), onPress: () => { pick(false); } },
          { icon: 'camera-outline' as const, title: t('Снять камерой'), onPress: () => { pick(true); } },
        ] : []),
        ...(f.file ? [{ icon: 'document-outline' as const, title: t('Файл (без сжатия)'), subtitle: t('В исходном качестве'), onPress: () => { pickFile(); } }] : []),
      ]} />
      <PhotoViewer photos={photos.map((m) => ({ id: m.id, url: m.url, name: m.sender_name, date: m.time }))} index={viewer} onClose={() => setViewerId(null)} headers={authHeaders()} />
      <PhotoEditor photo={editing} doneLabel={t('Отправить')} onDone={(uri) => { setEditing(null); if (uri) upload('photo', uri, 'photo.jpg', 'image/jpeg'); }} />
      <CallView ref={call} send={sendWs} name={thread?.title ?? ''} avatar={thread?.avatar} turn={thread?.turn ?? null} />
    </SafeAreaView>
  );
}
