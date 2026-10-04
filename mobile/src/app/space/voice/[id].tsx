import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Platform, Pressable, View } from 'react-native';

import { authHeaders, wsUrl } from '@/lib/api';
import { openSiteUrl } from '@/lib/links';
import { callsSupported, webrtc } from '@/lib/webrtc';
import { useApp } from '@/state/app';
import { Avatar, Button, Card, Icon, Screen, Txt } from '@/ui/kit';

type Peer = { peer: string; id?: number; name: string; avatar: string; muted?: boolean; on?: boolean };

/**
 * Голосовая комната сообщества. Звук идёт напрямую между участниками (WebRTC, каждый с каждым, до 8 человек) —
 * протокол тот же, что на сайте (static/js/voice.js, apps/chat/voice.py): вошедший сам звонит всем, кто уже в комнате.
 * WebRTC есть только в собранном приложении; в Expo Go комната открывается на сайте.
 */
export default function VoiceRoom() {
  const { id, title, web } = useLocalSearchParams<{ id: string; title?: string; web?: string }>();
  const { c, t } = useApp();
  const [state, setState] = useState<'idle' | 'joining' | 'in'>('idle');
  const [note, setNote] = useState('');
  const [people, setPeople] = useState<Peer[]>([]);
  const [muted, setMuted] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const stream = useRef<any>(null);
  const pcs = useRef<Record<string, any>>({});
  const ping = useRef<ReturnType<typeof setInterval> | null>(null);

  const leave = (text = '') => {
    if (ping.current) clearInterval(ping.current);
    Object.values(pcs.current).forEach((pc) => { try { pc.close(); } catch { /* уже закрыт */ } });
    pcs.current = {};
    if (ws.current) { ws.current.onclose = null; ws.current.close(); ws.current = null; }
    if (stream.current) { stream.current.getTracks().forEach((x: any) => x.stop()); stream.current = null; }
    setPeople([]);
    setMuted(false);
    setState('idle');
    setNote(text);
  };
  useEffect(() => () => leave(), []);          // ушли с экрана — вышли из комнаты

  const send = (o: object) => { if (ws.current?.readyState === 1) ws.current.send(JSON.stringify(o)); };
  const drop = (peer: string) => {
    try { pcs.current[peer]?.close(); } catch { /* уже закрыт */ }
    delete pcs.current[peer];
    setPeople((old) => old.filter((p) => p.peer !== peer));
  };
  const connect = async (info: Peer, initiator: boolean, ice: any[]) => {
    const pc = new webrtc!.RTCPeerConnection({ iceServers: ice });
    pcs.current[info.peer] = pc;
    setPeople((old) => [...old.filter((p) => p.peer !== info.peer), info]);
    stream.current.getTracks().forEach((track: any) => pc.addTrack(track, stream.current));
    pc.addEventListener('icecandidate', (e: any) => { if (e.candidate) send({ type: 'signal', to: info.peer, data: { candidate: e.candidate } }); });
    pc.addEventListener('connectionstatechange', () => {
      if (pc.connectionState === 'failed') drop(info.peer);
      else setPeople((old) => old.map((p) => (p.peer === info.peer ? { ...p, on: pc.connectionState === 'connected' } : p)));
    });
    if (initiator) {
      const offer = await pc.createOffer({});
      await pc.setLocalDescription(offer);
      send({ type: 'signal', to: info.peer, data: { sdp: pc.localDescription } });
    }
  };
  const onSignal = async (from: string, data: any) => {
    const pc = pcs.current[from];
    if (!pc) return;
    try {
      if (data.sdp) {
        await pc.setRemoteDescription(new webrtc!.RTCSessionDescription(data.sdp));
        if (data.sdp.type === 'offer') {
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          send({ type: 'signal', to: from, data: { sdp: pc.localDescription } });
        }
      } else if (data.candidate) await pc.addIceCandidate(new webrtc!.RTCIceCandidate(data.candidate));
    } catch { /* повторный сигнал — пропускаем */ }
  };

  const join = async () => {
    setState('joining');
    setNote('');
    try {
      stream.current = await webrtc!.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch {
      setState('idle');
      setNote(t('Нет доступа к микрофону — разрешите его в настройках телефона.'));
      return;
    }
    let ice: any[] = [];
    const sock: WebSocket = new (WebSocket as any)(wsUrl(`/ws/voice/${id}/`), null, { headers: authHeaders() });
    ws.current = sock;
    sock.onmessage = (e) => {
      const d = JSON.parse(String(e.data));
      if (d.type === 'hello') {
        ice = d.ice || [];
        setPeople([{ peer: d.me, name: t('Вы'), avatar: '', on: true }]);
        (d.peers as Peer[]).forEach((p) => connect(p, true, ice));
        setState('in');
        ping.current = setInterval(() => send({ type: 'ping' }), 25000);
      } else if (d.type === 'full') leave(t('В комнате уже максимум участников.'));
      else if (d.type === 'joined') connect(d, false, ice);
      else if (d.type === 'left') drop(d.peer);
      else if (d.type === 'signal') onSignal(d.from, d.data);
      else if (d.type === 'state') setPeople((old) => old.map((p) => (p.peer === d.peer ? { ...p, muted: d.muted } : p)));
    };
    sock.onclose = () => leave(t('Связь с комнатой прервалась.'));
  };
  const toggleMute = () => {
    const next = !muted;
    stream.current?.getAudioTracks().forEach((x: any) => { x.enabled = !next; });
    setMuted(next);
    setPeople((old) => old.map((p, i) => (i === 0 ? { ...p, muted: next } : p)));
    send({ type: 'state', muted: next });
  };

  if (!callsSupported || Platform.OS === 'web') {
    return (
      <Screen back title={title || t('Голосовая комната')}>
        <Card style={{ gap: 12, alignItems: 'center' }}>
          <Icon name="volume-medium-outline" size={44} color={c.accent} />
          <Txt style={{ textAlign: 'center', fontWeight: '700', fontSize: 16 }}>{t('Голос работает в установленном приложении')}</Txt>
          <Txt kind="muted" style={{ textAlign: 'center' }}>{t('В пробной версии (Expo Go) звонков и голосовых комнат нет. Пока можно войти в комнату через сайт.')}</Txt>
          {web ? <Button title={t('Открыть на сайте')} icon="open-outline" onPress={() => openSiteUrl(String(web))} style={{ alignSelf: 'stretch' }} /> : null}
        </Card>
      </Screen>
    );
  }

  return (
    <Screen back title={title || t('Голосовая комната')}>
      <Txt kind="muted" style={{ textAlign: 'center' }}>{state === 'in' ? t('В комнате: {n}', { n: people.length }) : note || t('До 8 человек. Звук идёт напрямую между участниками.')}</Txt>
      {people.length ? (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12, justifyContent: 'center' }}>
          {people.map((p) => (
            <View key={p.peer} style={{ width: '29%', alignItems: 'center', gap: 6, paddingVertical: 14, borderRadius: 20, backgroundColor: c.card, opacity: p.on === false ? 0.55 : 1 }}>
              <Avatar uri={p.avatar} name={p.name} size={58} hue={p.id ?? 2} />
              <Txt kind="small" numberOfLines={1} style={{ color: c.ink, fontWeight: '700' }}>{p.name}</Txt>
              {p.muted ? <Icon name="mic-off" size={15} color={c.bad} /> : <Icon name="mic" size={15} color={c.ok} />}
            </View>
          ))}
        </View>
      ) : null}
      {state === 'in' ? (
        <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 22, marginTop: 8 }}>
          <Pressable onPress={toggleMute} accessibilityLabel={t('Микрофон')} style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: muted ? c.card2 : c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
            <Icon name={muted ? 'mic-off' : 'mic'} size={27} color={muted ? c.bad : c.accentD} />
          </Pressable>
          <Pressable onPress={() => { leave(t('Вы вышли из комнаты.')); router.back(); }} accessibilityLabel={t('Выйти')} style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: c.bad, alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="call" size={26} color="#fff" style={{ transform: [{ rotate: '135deg' }] }} />
          </Pressable>
        </View>
      ) : <Button title={t('Войти в комнату')} icon="mic" onPress={join} loading={state === 'joining'} />}
    </Screen>
  );
}
