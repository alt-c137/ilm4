/**
 * Панель ввода чата «как в Telegram» (docs/MESSENGER.md §3):
 * - одна кнопка голос/кружок: короткое нажатие — переключить, удержание — запись;
 *   отпустил — отправилось, увёл влево — отмена, вверх — «замок» (запись без рук);
 * - долгое нажатие на «Отправить» — без звука или запланировать;
 * - анимации кнопок и подсказок (Reanimated).
 * Отправку делает экран чата (onText / onFile) — здесь только ввод и запись.
 */
/* eslint-disable react-hooks/refs, react-hooks/purity -- обработчики жестов (Gesture….runOnJS) и кнопок вызываются
   по касанию, а не во время отрисовки; React Compiler видит их создание при отрисовке и считает это ошибкой. */
import DateTimePicker, { DateTimePickerAndroid } from '@react-native-community/datetimepicker';
import { RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder } from 'expo-audio';
import { CameraView, useCameraPermissions, useMicrophonePermissions } from 'expo-camera';
import * as Haptics from 'expo-haptics';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Alert, Modal, Platform, Pressable, TextInput, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  FadeIn, FadeInDown, FadeOut, interpolate, useAnimatedStyle, useSharedValue, withRepeat, withSequence, withSpring, withTiming,
  ZoomIn, ZoomOut,
} from 'react-native-reanimated';

import { useApp } from '@/state/app';

import { Button, Icon, Txt } from './kit';
import { mmss } from './media';

export type SendOpts = { silent?: boolean; schedule?: string };
type Mode = 'voice' | 'circle';
type Rec = { kind: Mode; locked: boolean; started: number; cancelled: boolean; sendAfter: boolean; recording: boolean };

// голос — моно, 32 кбит/с, как в Telegram: речь звучит так же, а файл в несколько раз меньше «высокого качества»
const VOICE_PRESET = { ...RecordingPresets.HIGH_QUALITY, numberOfChannels: 1, bitRate: 32000, sampleRate: 24000 };

const HOLD_MS = 220;
const CANCEL_DX = -110;
const LOCK_DY = -70;
const LIMIT: Record<Mode, number> = { voice: 300, circle: 60 };

export function Composer({ features: f, busy, onText, onFile, onAttach }: {
  features: Record<string, any>;
  busy: boolean;
  onText: (body: string, opts?: SendOpts) => Promise<boolean>;
  onFile: (kind: Mode, uri: string, name: string, type: string, seconds: number) => void;
  onAttach?: () => void;
}) {
  const { c, t } = useApp();
  const canVoice = !!f.voice;
  const canCircle = !!f.circle && Platform.OS !== 'web';
  const [text, setText] = useState('');
  const [mode, setMode] = useState<Mode>(canVoice ? 'voice' : 'circle');
  const [rec, setRec] = useState<Rec | null>(null);
  const [sec, setSec] = useState(0);
  const [iosPicker, setIosPicker] = useState<Date | null>(null);
  const recRef = useRef<Rec | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const cam = useRef<CameraView>(null);
  const recorder = useAudioRecorder(VOICE_PRESET);
  const [camPerm, askCam] = useCameraPermissions();
  const [micPerm, askMic] = useMicrophonePermissions();

  const slideX = useSharedValue(0);
  const lockY = useSharedValue(0);
  const btnScale = useSharedValue(1);
  const arrow = useSharedValue(0);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);
  useEffect(() => {
    arrow.value = withRepeat(withSequence(withTiming(-4, { duration: 500 }), withTiming(0, { duration: 500 })), -1);
  }, [arrow]);

  const current = (): Rec | null => recRef.current;   // без сужения типа TypeScript после await
  const update = (r: Rec | null) => {
    recRef.current = r;
    setRec(r ? { ...r } : null);
  };

  const stopTimer = () => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  };
  const startTimer = (kind: Mode) => {
    setSec(0);
    stopTimer();
    timer.current = setInterval(() => {
      const r = recRef.current;
      if (!r) return;
      const s = Math.floor((Date.now() - r.started) / 1000);
      setSec(s);
      if (s >= LIMIT[kind]) finish(true);
    }, 250);
  };

  const reset = () => {
    stopTimer();
    slideX.value = withSpring(0);
    lockY.value = withSpring(0);
    btnScale.value = withSpring(1);
    update(null);
  };

  // ---------- запись ----------
  const start = async (kind: Mode) => {
    if (recRef.current) return;
    const r: Rec = { kind, locked: false, started: Date.now(), cancelled: false, sendAfter: false, recording: false };
    if (kind === 'voice') {
      const perm = await requestRecordingPermissionsAsync();
      if (!perm.granted) return Alert.alert(t('Нет доступа к микрофону'));
      update(r);
      btnScale.value = withSpring(1.5, { damping: 12 });
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
      await recorder.prepareToRecordAsync();
      if (current() !== r || r.cancelled) return;          // отпустили, пока готовился микрофон
      recorder.record();
      r.started = Date.now();
      r.recording = true;
    } else {
      if (!camPerm?.granted || !micPerm?.granted) {
        await askCam();
        await askMic();
        return Alert.alert(t('Доступ дан'), t('Теперь удерживайте кнопку, чтобы записать кружок.'));
      }
      update(r);                                          // камера появится, запись начнётся в onCameraReady
      btnScale.value = withSpring(1.5, { damping: 12 });
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    startTimer(kind);
  };

  const onCameraReady = async () => {
    const r = recRef.current;
    if (!r || r.kind !== 'circle' || r.recording || !cam.current) return;
    r.recording = true;
    r.started = Date.now();
    try {
      const res = await cam.current.recordAsync({ maxDuration: LIMIT.circle, maxFileSize: 24 * 1024 * 1024 });
      const seconds = Math.round((Date.now() - r.started) / 1000);
      if (res?.uri && r.sendAfter && seconds >= 1) {
        onFile('circle', res.uri, Platform.OS === 'ios' ? 'circle.mov' : 'circle.mp4', 'video/mp4', seconds);
      }
    } catch {
      // камера закрыта раньше времени — ничего не отправляем
    } finally {
      if (recRef.current === r) reset();
    }
  };

  const finish = async (send: boolean) => {
    const r = recRef.current;
    if (!r) return;
    r.sendAfter = send;
    r.cancelled = !send;
    const seconds = Math.round((Date.now() - r.started) / 1000);
    if (r.kind === 'voice') {
      reset();
      if (!r.recording) {
        if (send) Alert.alert(t('Удерживайте кнопку, чтобы записать'));
        return;
      }
      await recorder.stop();
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false });
      if (send && seconds >= 1 && recorder.uri) onFile('voice', recorder.uri, 'voice.m4a', 'audio/mp4', seconds);
      else if (send) Alert.alert(t('Слишком коротко — удерживайте кнопку'));
    } else if (r.recording) {
      cam.current?.stopRecording();                        // отправка — в onCameraReady после остановки
    } else {
      reset();
    }
  };

  const lock = () => {
    const r = recRef.current;
    if (!r || r.locked) return;
    r.locked = true;
    update(r);
    lockY.value = withSpring(0);
    btnScale.value = withSpring(1);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  };

  // ---------- жесты кнопки записи ----------
  const both = canVoice && canCircle;
  const tap = Gesture.Tap().maxDuration(HOLD_MS).runOnJS(true).onEnd((_e, ok) => {
    if (ok && both) {
      setMode((m) => (m === 'voice' ? 'circle' : 'voice'));
      Haptics.selectionAsync();
    }
  });
  const pan = Gesture.Pan().activateAfterLongPress(HOLD_MS).runOnJS(true)
    .onStart(() => { start(mode); })
    .onUpdate((e) => {
      const r = recRef.current;
      if (!r || r.locked || r.cancelled) return;
      slideX.value = Math.max(CANCEL_DX, Math.min(0, e.translationX));
      lockY.value = Math.max(LOCK_DY, Math.min(0, e.translationY));
      if (e.translationX <= CANCEL_DX) {
        finish(false);
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      } else if (e.translationY <= LOCK_DY) lock();
    })
    .onEnd(() => {
      const r = recRef.current;
      if (r && !r.locked && !r.cancelled) finish(true);
    });
  const gesture = Gesture.Race(pan, tap);

  // ---------- отправка текста и меню ----------
  const sendText = async (opts?: SendOpts) => {
    const body = text.trim();
    if (!body) return;
    if (await onText(body, opts)) setText('');
  };
  const pickSchedule = () => {
    const base = new Date(Date.now() + 3600e3);
    if (Platform.OS === 'android') {
      DateTimePickerAndroid.open({
        value: base, mode: 'date', minimumDate: new Date(),
        onChange: (e, d) => {
          if (e.type !== 'set' || !d) return;
          DateTimePickerAndroid.open({
            value: d, mode: 'time', is24Hour: true,
            onChange: (e2, d2) => { if (e2.type === 'set' && d2) confirmSchedule(d2); },
          });
        },
      });
    } else if (Platform.OS === 'ios') setIosPicker(base);
    else Alert.alert(t('Запланировать можно в приложении на телефоне.'));
  };
  const confirmSchedule = (d: Date) => {
    if (d.getTime() < Date.now() + 60e3) return Alert.alert(t('Выберите время хотя бы через минуту'));
    sendText({ schedule: d.toISOString() });
  };
  const menu = () => {
    if (!text.trim()) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    Alert.alert(t('Отправить'), undefined, [
      { text: t('Отправить без звука'), onPress: () => sendText({ silent: true }) },
      { text: t('Запланировать сообщение'), onPress: pickSchedule },
      { text: t('Отмена'), style: 'cancel' },
    ]);
  };

  // ---------- анимации ----------
  const slideStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: slideX.value }], opacity: interpolate(slideX.value, [CANCEL_DX, 0], [0.25, 1]),
  }));
  const lockStyle = useAnimatedStyle(() => ({ transform: [{ translateY: lockY.value / 2 }] }));
  const arrowStyle = useAnimatedStyle(() => ({ transform: [{ translateY: arrow.value }] }));
  const btnStyle = useAnimatedStyle(() => ({ transform: [{ scale: btnScale.value }] }));

  const canRecord = canVoice || canCircle;
  const recording = !!rec;
  const showSend = !recording && (!!text.trim() || !canRecord);
  const round = { width: 46, height: 46, borderRadius: 23, alignItems: 'center' as const, justifyContent: 'center' as const };

  return (
    <View>
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8, padding: 8, backgroundColor: c.card, borderTopWidth: 0.5, borderTopColor: c.line }}>
        {recording ? (
          <Animated.View entering={FadeIn.duration(150)} style={{ flex: 1, height: 46, flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 6 }}>
            {rec?.locked ? (
              <Pressable onPress={() => finish(false)} hitSlop={10} accessibilityLabel={t('Отменить запись')}>
                <Icon name="trash-outline" size={24} color={c.bad} />
              </Pressable>
            ) : null}
            <RecDot color={c.bad} />
            <Txt style={{ fontWeight: '800', fontVariant: ['tabular-nums'] }}>{mmss(sec)}</Txt>
            {rec?.locked ? (
              <Txt kind="small" numberOfLines={1} style={{ flex: 1 }}>{t('Без рук · ➤ — отправить')}</Txt>
            ) : (
              <Animated.View style={[{ flex: 1, alignItems: 'center' }, slideStyle]}>
                <Txt kind="small" numberOfLines={1}>‹ {t('влево — отмена')}</Txt>
              </Animated.View>
            )}
          </Animated.View>
        ) : (
          <>
            {onAttach ? (
              <Pressable onPress={onAttach} disabled={busy} style={{ padding: 8 }} accessibilityLabel={t('Отправить файл')}>
                {busy ? <ActivityIndicator color={c.accent} /> : <Icon name="attach" size={26} color={c.inkSoft} />}
              </Pressable>
            ) : null}
            <TextInput value={text} onChangeText={setText} placeholder={t('Сообщение')} placeholderTextColor={c.inkSoft} multiline maxLength={2000}
              style={{ flex: 1, maxHeight: 120, backgroundColor: c.card2, borderRadius: 20, paddingHorizontal: 14, paddingTop: 10, paddingBottom: 10, fontSize: 16, color: c.ink }} />
          </>
        )}

        {showSend ? (
          <Animated.View key="send" entering={ZoomIn.springify().damping(14)} exiting={ZoomOut.duration(120)}>
            <Pressable onPress={() => sendText()} onLongPress={menu} delayLongPress={400} disabled={!text.trim()}
              accessibilityLabel={t('Отправить')} accessibilityHint={t('Долгое нажатие — без звука или по расписанию')}
              style={[round, { backgroundColor: text.trim() ? c.accent : c.line }]}>
              <Icon name="send" size={20} color="#fff" />
            </Pressable>
          </Animated.View>
        ) : rec?.locked ? (
          <Animated.View key="locked-send" entering={ZoomIn.springify().damping(14)}>
            <Pressable onPress={() => finish(true)} accessibilityLabel={t('Отправить')} style={[round, { backgroundColor: c.accent }]}>
              <Icon name="send" size={20} color="#fff" />
            </Pressable>
          </Animated.View>
        ) : canRecord ? (
          <View>
            {recording ? (
              <Animated.View entering={FadeInDown.duration(200)} style={[{
                position: 'absolute', bottom: 64, left: 4, width: 38, paddingVertical: 8, borderRadius: 19, backgroundColor: c.card,
                alignItems: 'center', gap: 2, shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 10, elevation: 6,
              }, lockStyle]}>
                <Icon name="lock-closed-outline" size={18} color={c.inkSoft} />
                <Animated.View style={arrowStyle}><Icon name="chevron-up" size={16} color={c.inkSoft} /></Animated.View>
              </Animated.View>
            ) : null}
            <GestureDetector gesture={gesture}>
              <Animated.View key="rec" entering={ZoomIn.springify().damping(14)} style={[round, { backgroundColor: c.accent }, btnStyle]}
                accessible accessibilityRole="button"
                accessibilityLabel={mode === 'voice' ? t('Голосовое сообщение') : t('Видеокружок')}
                accessibilityHint={t('Нажмите — голос или кружок. Удерживайте — записать: отпустите — отправить, влево — отмена, вверх — без рук')}>
                <Animated.View key={mode} entering={ZoomIn.duration(180)} exiting={ZoomOut.duration(120)}>
                  <Icon name={mode === 'voice' ? 'mic' : 'aperture-outline'} size={22} color="#fff" />
                </Animated.View>
              </Animated.View>
            </GestureDetector>
          </View>
        ) : null}
      </View>

      {rec?.kind === 'circle' ? (
        // не Modal: окно перехватило бы касание, и удержание кнопки оборвалось бы
        <Animated.View entering={FadeIn.duration(150)} pointerEvents="box-none"
          style={{ position: 'absolute', left: 0, right: 0, bottom: '100%', height: 460, alignItems: 'center', justifyContent: 'center',
            gap: 16, backgroundColor: 'rgba(10,12,22,0.86)' }}>
          <Animated.View entering={ZoomIn.springify().damping(13)} pointerEvents="none"
            style={{ width: 260, height: 260, borderRadius: 130, overflow: 'hidden', borderWidth: 4, borderColor: '#e5484d' }}>
            <CameraView ref={cam} style={{ flex: 1 }} facing="front" mode="video" videoQuality="480p" videoBitrate={1_500_000}
              onCameraReady={onCameraReady} />
          </Animated.View>
          <Txt color="#fff" style={{ fontSize: 22, fontWeight: '800', fontVariant: ['tabular-nums'] }}>{mmss(sec)} / {mmss(LIMIT.circle)}</Txt>
          {rec.locked ? (
            <View style={{ flexDirection: 'row', gap: 12 }}>
              <Button kind="ghost" title={t('Отмена')} color="#fff" onPress={() => finish(false)} />
              <Button title={t('Отправить')} onPress={() => finish(true)} />
            </View>
          ) : (
            <Txt kind="small" color="rgba(255,255,255,0.8)">{t('Отпустите — отправить · влево — отмена · вверх — без рук')}</Txt>
          )}
        </Animated.View>
      ) : null}

      {iosPicker ? (
        <Modal transparent animationType="slide" onRequestClose={() => setIosPicker(null)}>
          <Pressable style={{ flex: 1, backgroundColor: c.overlay }} onPress={() => setIosPicker(null)} />
          <View style={{ backgroundColor: c.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 16, gap: 10 }}>
            <Txt kind="h3">{t('Запланировать сообщение')}</Txt>
            <DateTimePicker value={iosPicker} mode="datetime" display="inline" minimumDate={new Date()}
              onChange={(_e, d) => { if (d) setIosPicker(d); }} />
            <Button title={t('Запланировать')} onPress={() => { const d = iosPicker; setIosPicker(null); confirmSchedule(d); }} />
          </View>
        </Modal>
      ) : null}
    </View>
  );
}

function RecDot({ color }: { color: string }) {
  const o = useSharedValue(1);
  useEffect(() => {
    o.value = withRepeat(withTiming(0.3, { duration: 600 }), -1, true);
  }, [o]);
  const style = useAnimatedStyle(() => ({ opacity: o.value }));
  return <Animated.View exiting={FadeOut} style={[{ width: 12, height: 12, borderRadius: 6, backgroundColor: color }, style]} />;
}
