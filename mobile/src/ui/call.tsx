/** Звонок в приложении: тот же протокол, что на сайте (static/js/chat.js), поэтому приложение и сайт
 *  звонят друг другу. Сигналы идут через WebSocket чата, голос и видео — напрямую между телефонами. */
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { Alert, Modal, Pressable, View } from 'react-native';
import Animated, { ZoomIn } from 'react-native-reanimated';

import { callEmoji } from '@/lib/callEmoji';
import { webrtc } from '@/lib/webrtc';
import { useApp } from '@/state/app';

import { Avatar, Icon, Txt } from './kit';
import { mmss } from './media';

type Ice = { url: string; username: string; credential: string } | null;
export type CallHandle = { start: (video: boolean) => void; onSignal: (d: any) => void; answerNext: () => void };

type C = { role: 'caller' | 'callee'; video: boolean; pc?: any; local?: any; start?: number; pendingIce: any[];
  ringT?: ReturnType<typeof setInterval>; timeoutT?: ReturnType<typeof setTimeout> };

export const CallView = forwardRef<CallHandle, { send: (o: object) => void; name: string; avatar?: string; turn: Ice }>(
  function CallView({ send, name, avatar, turn }, ref) {
    const { t } = useApp();
    const c = useRef<C | null>(null);
    const [state, setState] = useState<'idle' | 'ringing' | 'incoming' | 'connecting' | 'active'>('idle');
    const [remote, setRemote] = useState<any>(null);
    const [local, setLocal] = useState<any>(null);
    const [sec, setSec] = useState(0);
    const [muted, setMuted] = useState(false);
    const [video, setVideo] = useState(false);
    const [emoji, setEmoji] = useState<string[]>([]);
    const [emojiInfo, setEmojiInfo] = useState(false);
    const auto = useRef(false);

    const ice = [{ urls: ['stun:stun.l.google.com:19302', 'stun:stun1.l.google.com:19302'] },
      ...(turn?.url ? [{ urls: turn.url, username: turn.username, credential: turn.credential }] : [])];

    useEffect(() => {
      if (state !== 'active') return;
      const id = setInterval(() => setSec(c.current?.start ? Math.round((Date.now() - c.current.start) / 1000) : 0), 1000);
      return () => clearInterval(id);
    }, [state]);

    const media = (v: boolean) => webrtc!.mediaDevices.getUserMedia({ audio: true, video: v ? { facingMode: 'user', width: 1280, height: 720 } : false });

    const cleanup = () => {
      const x = c.current;
      if (!x) return;
      if (x.ringT) clearInterval(x.ringT);
      if (x.timeoutT) clearTimeout(x.timeoutT);
      try { x.pc?.close(); } catch { /* уже закрыт */ }
      x.local?.getTracks().forEach((tr: any) => tr.stop());
      c.current = null;
      setRemote(null);
      setLocal(null);
      setMuted(false);
      setSec(0);
      setEmoji([]);
      setEmojiInfo(false);
      setState('idle');
    };

    const finish = (sendEnd: boolean, outcome?: string) => {
      const x = c.current;
      if (!x) return;
      if (sendEnd) send({ type: 'signal', action: 'end' });
      if (x.role === 'caller') {
        const dur = x.start ? (Date.now() - x.start) / 1000 : 0;
        send({ type: 'calllog', video: x.video, duration: Math.round(dur), outcome: outcome || (x.start ? 'done' : 'cancelled') });
      }
      cleanup();
    };

    const peer = () => {
      const x = c.current!;
      const pc = new webrtc!.RTCPeerConnection({ iceServers: ice });
      x.local.getTracks().forEach((tr: any) => pc.addTrack(tr, x.local));
      pc.addEventListener('icecandidate', (e: any) => { if (e.candidate) send({ type: 'signal', action: 'ice', candidate: e.candidate }); });
      pc.addEventListener('track', (e: any) => { if (e.streams?.[0]) setRemote(e.streams[0]); });
      pc.addEventListener('connectionstatechange', () => {
        if (!c.current) return;
        if (pc.connectionState === 'connected' && !c.current.start) {
          c.current.start = Date.now();
          setState('active');
          // 4 эмодзи из отпечатков ключей обеих сторон — как в Telegram (docs/MESSENGER.md §2.3)
          callEmoji(pc.localDescription?.sdp, pc.remoteDescription?.sdp).then((e) => { if (c.current) setEmoji(e); }).catch(() => {});
        }
        if (pc.connectionState === 'failed') {
          Alert.alert(t('Не удалось соединиться. Возможно, нужна настройка TURN-сервера.'));
          finish(true);
        }
      });
      x.pc = pc;
      return pc;
    };

    const flushIce = () => {
      const x = c.current;
      if (!x?.pc) return;
      x.pendingIce.forEach((cand) => x.pc.addIceCandidate(new webrtc!.RTCIceCandidate(cand)).catch(() => {}));
      x.pendingIce = [];
    };

    const start = async (v: boolean) => {
      if (c.current || !webrtc) return;
      c.current = { role: 'caller', video: v, pendingIce: [] };
      setVideo(v);
      setState('ringing');
      try {
        const stream = await media(v);
        if (!c.current) { stream.getTracks().forEach((tr: any) => tr.stop()); return; }
        c.current.local = stream;
        setLocal(stream);
        const ring = () => send({ type: 'signal', action: 'ring', video: v });
        ring();
        c.current.ringT = setInterval(ring, 3000);   // повтор: собеседник мог открыть чат позже
        c.current.timeoutT = setTimeout(() => { finish(true, 'missed'); Alert.alert(t('Не отвечает')); }, 45000);
      } catch {
        cleanup();
        Alert.alert(v ? t('Нет доступа к камере') : t('Нет доступа к микрофону'));
      }
    };

    const accept = async () => {
      const x = c.current;
      if (!x || x.role !== 'callee') return;
      setState('connecting');
      try {
        const stream = await media(x.video);
        if (!c.current) { stream.getTracks().forEach((tr: any) => tr.stop()); return; }
        c.current.local = stream;
        setLocal(stream);
        send({ type: 'signal', action: 'accept' });
      } catch {
        Alert.alert(x.video ? t('Нет доступа к камере') : t('Нет доступа к микрофону'));
        decline();
      }
    };
    const decline = () => {
      if (!c.current) return;
      send({ type: 'signal', action: 'decline' });
      cleanup();
    };

    const onSignal = async (d: any) => {
      const a = d.action;
      if (a === 'ring') {
        if (c.current || !webrtc) return;
        c.current = { role: 'callee', video: !!d.video, pendingIce: [] };
        setVideo(!!d.video);
        setState('incoming');
        if (auto.current) { auto.current = false; accept(); }
        return;
      }
      const x = c.current;
      if (!x) return;
      try {
        if (a === 'accept' && x.role === 'caller' && !x.pc) {
          if (x.ringT) clearInterval(x.ringT);
          if (x.timeoutT) clearTimeout(x.timeoutT);
          setState('connecting');
          const pc = peer();
          const offer = await pc.createOffer({});
          await pc.setLocalDescription(offer);
          send({ type: 'signal', action: 'offer', sdp: pc.localDescription });
        } else if (a === 'offer' && x.role === 'callee') {
          const pc = peer();
          await pc.setRemoteDescription(new webrtc!.RTCSessionDescription(d.sdp));
          flushIce();
          const ans = await pc.createAnswer();
          await pc.setLocalDescription(ans);
          send({ type: 'signal', action: 'answer', sdp: pc.localDescription });
        } else if (a === 'answer' && x.role === 'caller' && x.pc) {
          await x.pc.setRemoteDescription(new webrtc!.RTCSessionDescription(d.sdp));
          flushIce();
        } else if (a === 'ice') {
          if (x.pc?.remoteDescription) x.pc.addIceCandidate(new webrtc!.RTCIceCandidate(d.candidate)).catch(() => {});
          else x.pendingIce.push(d.candidate);
        } else if (a === 'decline') {
          Alert.alert(t('Звонок отклонён'));
          finish(false, 'declined');
        } else if (a === 'end') {
          finish(false);
        }
      } catch {
        finish(true);
      }
    };

    useImperativeHandle(ref, () => ({ start, onSignal, answerNext: () => { auto.current = true; } }));

    const toggleMute = () => {
      const tr = c.current?.local?.getAudioTracks()[0];
      if (!tr) return;
      tr.enabled = !tr.enabled;
      setMuted(!tr.enabled);
    };
    const flip = () => {
      const tr = c.current?.local?.getVideoTracks()[0];
      tr?._switchCamera?.();
    };

    if (state === 'idle' || !webrtc) return null;
    const RTCView = webrtc.RTCView;
    const label = { ringing: t('Звоним…'), incoming: video ? t('Входящий видеозвонок') : t('Входящий аудиозвонок'),
      connecting: t('Соединение…'), active: mmss(sec), idle: '' }[state];

    return (
      <Modal visible animationType="slide" onRequestClose={() => finish(true)}>
        <View style={{ flex: 1, backgroundColor: '#0e1016' }}>
          {video && remote ? <RTCView streamURL={remote.toURL()} style={{ position: 'absolute', inset: 0 }} objectFit="cover" /> : null}
          {video && local ? (
            <RTCView streamURL={local.toURL()} mirror zOrder={1} objectFit="cover"
              style={{ position: 'absolute', right: 16, top: 60, width: 110, height: 160, borderRadius: 14, overflow: 'hidden' }} />
          ) : null}
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14 }}>
            {!(video && remote) ? <Avatar uri={avatar} name={name} size={110} /> : null}
            <Txt color="#fff" style={{ fontSize: 24, fontWeight: '800' }}>{name}</Txt>
            <Txt color="rgba(255,255,255,0.8)">{label}</Txt>
            {emoji.length ? (
              <Animated.View entering={ZoomIn.springify().damping(12)}>
              <Pressable onPress={() => setEmojiInfo((v) => !v)} accessibilityLabel={t('Проверка шифрования')}
                style={{ backgroundColor: 'rgba(255,255,255,0.12)', borderRadius: 999, paddingHorizontal: 16, paddingVertical: 6 }}>
                <Txt style={{ fontSize: 26, letterSpacing: 6 }}>{emoji.join(' ')}</Txt>
              </Pressable>
              </Animated.View>
            ) : null}
            {emojiInfo ? (
              <Txt color="#fff" kind="small" style={{ maxWidth: 300, textAlign: 'center', backgroundColor: 'rgba(0,0,0,0.45)', borderRadius: 14, padding: 10 }}>
                {t('Звонок зашифрован сквозным шифрованием: ключи создались на ваших устройствах, сервер их не знает. Если у собеседника те же 4 эмодзи — посередине никого нет.')}
              </Txt>
            ) : null}
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 26, paddingBottom: 60 }}>
            {state === 'incoming' ? (
              <>
                <RoundBtn icon="call" bg="#e5484d" rotate onPress={decline} />
                <RoundBtn icon={video ? 'videocam' : 'call'} bg="#12a150" onPress={accept} />
              </>
            ) : (
              <>
                <RoundBtn icon={muted ? 'mic-off' : 'mic'} bg={muted ? '#fff3' : '#ffffff22'} onPress={toggleMute} />
                {video ? <RoundBtn icon="camera-reverse" bg="#ffffff22" onPress={flip} /> : null}
                <RoundBtn icon="call" bg="#e5484d" rotate onPress={() => finish(true)} />
              </>
            )}
          </View>
        </View>
      </Modal>
    );
  });

function RoundBtn({ icon, bg, onPress, rotate }: { icon: any; bg: string; onPress: () => void; rotate?: boolean }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => ({ width: 68, height: 68, borderRadius: 34, backgroundColor: bg, alignItems: 'center', justifyContent: 'center', opacity: pressed ? 0.7 : 1 })}>
      <Icon name={icon} size={30} color="#fff" style={rotate ? { transform: [{ rotate: '135deg' }] } : undefined} />
    </Pressable>
  );
}
