/** Вложения чата: фото, видео, голосовые, кружки. Файлы отдаются только участникам — по токену. */
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { Image } from 'expo-image';
import { useVideoPlayer, VideoView } from 'expo-video';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import { useState } from 'react';
import { ActivityIndicator, Alert, Modal, Pressable, useWindowDimensions, View } from 'react-native';

import { authHeaders } from '@/lib/api';
import { useApp } from '@/state/app';

import { Icon, Txt } from './kit';

export function mmss(sec: number) {
  const s = Math.max(0, Math.round(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/** Размер фото в сообщении — правило Telegram: свои пропорции, не шире и не выше отведённого места, без обрезки. */
export function photoBox(w: number, h: number, maxW: number, maxH: number) {
  if (!w || !h) return { width: Math.min(230, maxW), height: Math.min(230, maxW) };
  const ratio = h / w;
  let width = Math.min(w, maxW), height = width * ratio;
  if (height > maxH) { height = maxH; width = maxH / ratio; }
  return { width: Math.max(90, Math.round(width)), height: Math.max(60, Math.round(height)) };
}

export function ChatPhoto({ uri, onPress, w = 0, h = 0 }: { uri: string; onPress?: () => void; w?: number; h?: number }) {
  const [open, setOpen] = useState(false);
  const win = useWindowDimensions();
  const [real, setReal] = useState<{ w: number; h: number } | null>(null);       // старые фото без сохранённых размеров
  const box = photoBox(w || real?.w || 0, h || real?.h || 0, Math.min(300, win.width * 0.72), 360);
  const src = { uri, headers: authHeaders() };
  return (
    <>
      {/* onPress — экран чата открывает общий просмотр, где листаются все фото переписки */}
      <Pressable onPress={onPress ?? (() => setOpen(true))}>
        <Image source={src} style={{ ...box, borderRadius: 14, backgroundColor: '#0002' }} contentFit="cover" transition={120}
          onLoad={w ? undefined : (e) => setReal({ w: e.source.width, h: e.source.height })} />
      </Pressable>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={{ flex: 1, backgroundColor: '#000', justifyContent: 'center' }} onPress={() => setOpen(false)}>
          <Image source={src} style={{ width: '100%', height: '80%' }} contentFit="contain" />
          <View style={{ position: 'absolute', top: 50, right: 20 }}><Icon name="close" size={30} color="#fff" /></View>
        </Pressable>
      </Modal>
    </>
  );
}

export function ChatVideo({ uri, round }: { uri: string; round?: boolean }) {
  const player = useVideoPlayer({ uri, headers: authHeaders() }, (p) => {
    p.loop = !!round;
  });
  const size = round ? 200 : 240;
  return (
    <View style={{ width: size, height: round ? size : 180, borderRadius: round ? size / 2 : 14, overflow: 'hidden', backgroundColor: '#000' }}>
      <VideoView player={player} style={{ width: '100%', height: '100%' }} contentFit="cover" nativeControls={!round}
        fullscreenOptions={{ enable: !round }} />
      {round ? <Pressable style={{ position: 'absolute', inset: 0 }} onPress={() => (player.playing ? player.pause() : player.play())} /> : null}
    </View>
  );
}

export function ChatVoice({ uri, duration, mine }: { uri: string; duration: number; mine: boolean }) {
  const { c } = useApp();
  const player = useAudioPlayer({ uri, headers: authHeaders() });
  const st = useAudioPlayerStatus(player);
  const total = st.duration || duration || 1;
  const pos = st.currentTime || 0;
  const fg = mine ? '#fff' : c.accent;
  const [rate, setRate] = useState(1);
  const speed = () => {                       // скорость: 1× → 1,5× → 2× (как в Telegram)
    const next = rate === 1 ? 1.5 : rate === 1.5 ? 2 : 1;
    setRate(next);
    try { player.setPlaybackRate(next); } catch { /* старое устройство без смены скорости */ }
  };
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, minWidth: 190 }}>
      <Pressable onPress={() => {
        if (st.playing) player.pause();
        else {
          if (st.didJustFinish || pos >= total - 0.2) player.seekTo(0);
          player.play();
        }
      }} style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: mine ? 'rgba(255,255,255,0.25)' : c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
        <Icon name={st.playing ? 'pause' : 'play'} size={20} color={fg} />
      </Pressable>
      <View style={{ flex: 1, height: 4, borderRadius: 2, backgroundColor: mine ? 'rgba(255,255,255,0.3)' : c.line }}>
        <View style={{ width: `${Math.min(100, (pos / total) * 100)}%`, height: 4, borderRadius: 2, backgroundColor: fg }} />
      </View>
      <Txt kind="small" color={mine ? '#fff' : c.inkSoft}>{mmss(st.playing ? pos : total)}</Txt>
      <Pressable onPress={speed} hitSlop={8} style={{ minWidth: 34, height: 22, paddingHorizontal: 6, borderRadius: 11, alignItems: 'center', justifyContent: 'center',
        backgroundColor: mine ? 'rgba(255,255,255,0.24)' : c.accentSoft }}>
        <Txt kind="small" color={mine ? '#fff' : c.accentD} style={{ fontSize: 11.5, fontWeight: '800' }}>{String(rate).replace('.', ',')}×</Txt>
      </Pressable>
    </View>
  );
}

export function fileSize(n: number, t: (s: string) => string) {
  if (n < 1024) return `${n} ${t('Б')}`;
  if (n < 1048576) return `${Math.round(n / 1024)} ${t('КБ')}`;
  if (n < 1073741824) return `${(n / 1048576).toFixed(1).replace('.0', '')} ${t('МБ')}`;
  return `${(n / 1073741824).toFixed(2).replace(/\.?0+$/, '')} ${t('ГБ')}`;
}

/** «Отправлено файлом»: скачиваем (со входом по токену) и открываем меню «Открыть / Сохранить». */
export function ChatFile({ uri, name, size, mine }: { uri: string; name: string; size: number; mine: boolean }) {
  const { c, t } = useApp();
  const [busy, setBusy] = useState(false);
  const open = async () => {
    setBusy(true);
    try {
      const safe = (name || 'file').replace(/[^\p{L}\p{N}._ -]/gu, '_');
      const res = await FileSystem.downloadAsync(uri, `${FileSystem.cacheDirectory}${safe}`, { headers: authHeaders() });
      if (res.status !== 200) throw new Error(t('Не удалось скачать файл'));
      if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(res.uri, { dialogTitle: name });
      else Alert.alert(t('Файл скачан'), res.uri);
    } catch (e: any) {
      Alert.alert(e.message);
    } finally {
      setBusy(false);
    }
  };
  const fg = mine ? '#fff' : c.accent;
  return (
    <Pressable onPress={open} disabled={busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, minWidth: 200, padding: 6 }}>
      <View style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: mine ? 'rgba(255,255,255,0.25)' : c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
        {busy ? <ActivityIndicator color={fg} /> : <Icon name="document-outline" size={22} color={fg} />}
      </View>
      <View style={{ flex: 1 }}>
        <Txt color={mine ? '#fff' : c.ink} style={{ fontWeight: '700' }} numberOfLines={2}>{name || t('Файл')}</Txt>
        <Txt kind="small" color={mine ? 'rgba(255,255,255,0.8)' : c.inkSoft}>{fileSize(size, t)}</Txt>
      </View>
    </Pressable>
  );
}
