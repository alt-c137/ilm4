/**
 * Панель ввода чата — по образцу Telegram (docs/MESSENGER.md §3):
 * - одна кнопка голос/кружок: короткое нажатие — переключить, удержание — запись;
 *   отпустил — отправилось, увёл влево — отмена, вверх — «замок» (запись без рук);
 * - во время записи: красная точка, время с десятыми, «‹ Влево — отмена»; кнопка под пальцем
 *   вырастает и «дышит» волной, над ней — замок; в «замке» — пауза, «ОТМЕНА» посередине и ➤;
 * - кружок: переписка затемняется, большой круг с камерой по центру, слева снизу — смена камеры и фонарик;
 * - долгое нажатие на «Отправить» — без звука или запланировать.
 * Отправку делает экран чата (onText / onFile) — здесь только ввод и запись.
 */
/* eslint-disable react-hooks/refs, react-hooks/purity -- обработчики жестов (Gesture….runOnJS) и кнопок вызываются
   по касанию, а не во время отрисовки; React Compiler видит их создание при отрисовке и считает это ошибкой. */
import DateTimePicker, { DateTimePickerAndroid } from '@react-native-community/datetimepicker';
import { RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder } from 'expo-audio';
import { CameraView, useCameraPermissions, useMicrophonePermissions } from 'expo-camera';
import * as Haptics from 'expo-haptics';
import { useEffect, useImperativeHandle, useRef, useState, type Ref } from 'react';
import { ActivityIndicator, Alert, Modal, Platform, Pressable, Text, TextInput, useWindowDimensions, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Svg, { Circle as SvgCircle } from 'react-native-svg';
import Animated, {
  FadeIn, FadeInDown, FadeOut, interpolate, useAnimatedStyle, useSharedValue, withRepeat, withSequence, withTiming,
  ZoomIn, ZoomOut,
} from 'react-native-reanimated';

import { useApp } from '@/state/app';

import { Button, Icon, Txt } from './kit';

export type SendOpts = { silent?: boolean; schedule?: string };
/** Полоска над полем ввода: ответ на сообщение или правка своего (как в Telegram). */
export type Banner = { kind: 'reply' | 'edit'; title: string; text: string };
export type ComposerHandle = { setText: (text: string) => void; getText: () => string; focus: () => void };
type Mode = 'voice' | 'circle';
type Rec = { kind: Mode; locked: boolean; started: number; cancelled: boolean; sendAfter: boolean; recording: boolean;
  idle: number; pausedAt: number; gen: number };

/** Сколько длится запись (без пауз), в секундах. */
function elapsed(r: Rec) {
  return Math.max(0, (Date.now() - r.started - r.idle - (r.pausedAt ? Date.now() - r.pausedAt : 0)) / 1000);
}
/** Время записи, как в Telegram: 0:07,2 */
function clock(s: number) {
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')},${Math.floor((s * 10) % 10)}`;
}

// голос — моно, 32 кбит/с, как в Telegram: речь звучит так же, а файл в несколько раз меньше «высокого качества»
const VOICE_PRESET = { ...RecordingPresets.HIGH_QUALITY, numberOfChannels: 1, bitRate: 32000, sampleRate: 24000 };

const HOLD_MS = 220;
const CANCEL_DX = -110;
const LOCK_DY = -70;
const LIMIT: Record<Mode, number> = { voice: 300, circle: 60 };

export function Composer({ features: f, busy, onText, onFile, onAttach, banner, onBannerClose, onChange, onTyping, ref }: {
  features: Record<string, any>;
  busy: boolean;
  onText: (body: string, opts?: SendOpts) => Promise<boolean>;
  onFile: (kind: Mode, uri: string, name: string, type: string, seconds: number) => void;
  onAttach?: () => void;
  banner?: Banner | null;
  onBannerClose?: () => void;
  onChange?: (text: string) => void;                       // для черновика
  onTyping?: (what: 'text' | 'voice' | 'circle') => void;   // «печатает…», «записывает голосовое»
  ref?: Ref<ComposerHandle>;
}) {
  const { c, t } = useApp();
  const field = useRef<TextInput>(null);
  const win = useWindowDimensions();
  const canVoice = !!f.voice;
  const canCircle = !!f.circle && Platform.OS !== 'web';
  const [text, setTextState] = useState('');
  const latest = useRef('');
  const setText = (v: string) => {
    latest.current = v;
    setTextState(v);
    onChange?.(v);
    if (v.trim()) onTyping?.('text');
  };
  useImperativeHandle(ref, () => ({
    setText: (v: string) => { latest.current = v; setTextState(v); },
    getText: () => latest.current,
    focus: () => field.current?.focus(),
  }), []);
  const [mode, setMode] = useState<Mode>(canVoice ? 'voice' : 'circle');
  const [rec, setRec] = useState<Rec | null>(null);
  const [sec, setSec] = useState(0);
  const [iosPicker, setIosPicker] = useState<Date | null>(null);
  const [sel, setSel] = useState({ start: 0, end: 0 });
  const [facing, setFacing] = useState<'front' | 'back'>('front');
  const [torch, setTorch] = useState(false);
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
  const wave = useSharedValue(0);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);
  useEffect(() => {
    arrow.value = withRepeat(withSequence(withTiming(-4, { duration: 500 }), withTiming(0, { duration: 500 })), -1);
    wave.value = withRepeat(withTiming(1, { duration: 900 }), -1, true);
  }, [arrow, wave]);

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
      const s = r.recording ? elapsed(r) : 0;
      setSec(s);
      if (s >= LIMIT[kind]) finish(true);
    }, 100);
  };

  const reset = () => {
    stopTimer();
    slideX.value = withTiming(0, { duration: 140 });
    lockY.value = withTiming(0, { duration: 140 });
    btnScale.value = withTiming(1, { duration: 140 });
    update(null);
  };

  // ---------- запись ----------
  const start = async (kind: Mode) => {
    if (recRef.current) return;
    const r: Rec = { kind, locked: false, started: Date.now(), cancelled: false, sendAfter: false, recording: false,
      idle: 0, pausedAt: 0, gen: 0 };
    if (kind === 'voice') {
      const perm = await requestRecordingPermissionsAsync();
      if (!perm.granted) return Alert.alert(t('Нет доступа к микрофону'));
      update(r);
      btnScale.value = withTiming(2, { duration: 160 });
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
      setFacing('front');
      setTorch(false);
      update(r);                                          // камера появится, запись начнётся в onCameraReady
      btnScale.value = withTiming(2, { duration: 160 });
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    startTimer(kind);
    onTyping?.(kind);
  };

  const onCameraReady = async () => {
    const r = recRef.current;
    if (!r || r.kind !== 'circle' || r.recording || !cam.current) return;
    const gen = r.gen;                                    // сменили камеру — прежняя запись «устарела»
    r.recording = true;
    r.started = Date.now();
    r.idle = 0;
    try {
      const res = await cam.current.recordAsync({ maxDuration: LIMIT.circle, maxFileSize: 24 * 1024 * 1024 });
      const seconds = Math.round(elapsed(r));
      if (res?.uri && r.gen === gen && r.sendAfter && seconds >= 1) {
        onFile('circle', res.uri, Platform.OS === 'ios' ? 'circle.mov' : 'circle.mp4', 'video/mp4', seconds);
      }
    } catch {
      // камера закрыта раньше времени — ничего не отправляем
    } finally {
      if (recRef.current === r && r.gen === gen) reset();
    }
  };

  // другая камера: кружок начинается заново (камера телефона не умеет переключаться посреди записи)
  const flip = () => {
    const r = recRef.current;
    if (!r || r.kind !== 'circle') return;
    r.gen += 1;
    r.recording = false;
    setTorch(false);
    setFacing((x) => (x === 'front' ? 'back' : 'front'));
    Haptics.selectionAsync();
  };

  // пауза в «замке» (голос): остановить и продолжить; время на паузе не считается
  const togglePause = () => {
    const r = recRef.current;
    if (!r || r.kind !== 'voice' || !r.recording) return;
    if (r.pausedAt) {
      r.idle += Date.now() - r.pausedAt;
      r.pausedAt = 0;
      recorder.record();
    } else {
      r.pausedAt = Date.now();
      recorder.pause();
    }
    update(r);
    Haptics.selectionAsync();
  };

  const finish = async (send: boolean) => {
    const r = recRef.current;
    if (!r) return;
    r.sendAfter = send;
    r.cancelled = !send;
    const seconds = Math.round(elapsed(r));
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
    slideX.value = withTiming(0, { duration: 140 });
    lockY.value = withTiming(0, { duration: 140 });
    btnScale.value = withTiming(1.35, { duration: 160 });
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  };

  // ---------- жесты кнопки записи ----------
  const both = canVoice && canCircle;
  const tap = Gesture.Tap().maxDuration(HOLD_MS).runOnJS(true).onEnd((_e, ok) => {
    if (ok && recRef.current?.locked) finish(true);       // в «замке» кнопка — «отправить»
    else if (ok && both && !recRef.current) {
      setMode((m) => (m === 'voice' ? 'circle' : 'voice'));
      Haptics.selectionAsync();
    }
  });
  const pan = Gesture.Pan().activateAfterLongPress(HOLD_MS).runOnJS(true)
    .onStart(() => {
      if (recRef.current?.locked) finish(true);
      else start(mode);
    })
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

  // оформление выделенного текста, как в Telegram: жирный, курсив, зачёркнутый, код, скрытый
  const format = (mark: string) => {
    const { start, end } = sel;
    if (end <= start) return;
    setText(text.slice(0, start) + mark + text.slice(start, end) + mark + text.slice(end));
    setSel({ start: 0, end: 0 });
    Haptics.selectionAsync();
  };

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
    transform: [{ translateX: slideX.value * 0.6 }], opacity: interpolate(slideX.value, [CANCEL_DX, 0], [0.2, 1]),
  }));
  const lockStyle = useAnimatedStyle(() => ({ transform: [{ translateY: lockY.value / 2 }] }));
  const arrowStyle = useAnimatedStyle(() => ({ transform: [{ translateY: arrow.value }] }));
  // кнопка едет за пальцем; выросшая — чуть отходит от края, чтобы круг был виден целиком
  const btnStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: slideX.value + interpolate(btnScale.value, [1, 2], [0, -20]) },
      { translateY: lockY.value + interpolate(btnScale.value, [1, 2], [0, -16]) },
      { scale: btnScale.value },
    ],
  }));
  const wave1 = useAnimatedStyle(() => ({ transform: [{ scale: 1.12 + wave.value * 0.16 }], opacity: 0.26 }));
  const wave2 = useAnimatedStyle(() => ({ transform: [{ scale: 1.26 + (1 - wave.value) * 0.18 }], opacity: 0.13 }));

  const canRecord = canVoice || canCircle;
  const recording = !!rec;
  const showSend = !recording && (!!text.trim() || !canRecord || banner?.kind === 'edit');
  const round = { width: 46, height: 46, borderRadius: 23, alignItems: 'center' as const, justifyContent: 'center' as const };
  const shadow = { shadowColor: c.accent, shadowOpacity: 0.35, shadowRadius: 8, shadowOffset: { width: 0, height: 3 }, elevation: 3 };
  const floating = { position: 'absolute' as const, backgroundColor: c.card, alignItems: 'center' as const, justifyContent: 'center' as const,
    shadowColor: '#000', shadowOpacity: 0.22, shadowRadius: 10, shadowOffset: { width: 0, height: 3 }, elevation: 6 };
  const circleSize = Math.min(win.width - 36, win.height * 0.5, 380);

  return (
    <View>
      {rec?.kind === 'circle' ? (
        // не Modal: окно перехватило бы касание, и удержание кнопки оборвалось бы
        <Animated.View entering={FadeIn.duration(180)} exiting={FadeOut.duration(140)} pointerEvents="box-none"
          style={{ position: 'absolute', left: 0, right: 0, bottom: '100%', height: win.height, alignItems: 'center', justifyContent: 'center',
            backgroundColor: 'rgba(10,12,22,0.84)' }}>
          {/* круг с камерой: появляется спокойно, без «прыжка»; вокруг — полоска, сколько записано из минуты */}
          <View pointerEvents="none" style={{ width: circleSize + 16, height: circleSize + 16, alignItems: 'center', justifyContent: 'center', marginTop: win.height * 0.16 }}>
            <View style={{ width: circleSize, height: circleSize, borderRadius: circleSize / 2, overflow: 'hidden', backgroundColor: '#000' }}>
              <CameraView key={facing} ref={cam} style={{ flex: 1 }} facing={facing} enableTorch={torch} mode="video" videoQuality="480p"
                videoBitrate={1_500_000} onCameraReady={onCameraReady} />
            </View>
            <Svg width={circleSize + 16} height={circleSize + 16} style={{ position: 'absolute', transform: [{ rotate: '-90deg' }] }}>
              <SvgCircle cx={(circleSize + 16) / 2} cy={(circleSize + 16) / 2} r={circleSize / 2 + 4} stroke="rgba(255,255,255,0.22)" strokeWidth={3} fill="none" />
              <SvgCircle cx={(circleSize + 16) / 2} cy={(circleSize + 16) / 2} r={circleSize / 2 + 4} stroke="#fff" strokeWidth={3} fill="none" strokeLinecap="round"
                strokeDasharray={`${Math.PI * (circleSize + 8)}`} strokeDashoffset={Math.PI * (circleSize + 8) * (1 - Math.min(1, sec / LIMIT.circle))} />
            </Svg>
          </View>
          <View style={{ position: 'absolute', left: 12, bottom: 14, flexDirection: 'row', backgroundColor: 'rgba(30,34,48,0.9)', borderRadius: 23 }}>
            <Pressable onPress={flip} hitSlop={6} accessibilityLabel={t('Другая камера')} style={{ width: 48, height: 46, alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="camera-reverse-outline" size={23} color="#fff" />
            </Pressable>
            {facing === 'back' ? (
              <Pressable onPress={() => setTorch((x) => !x)} hitSlop={6} accessibilityLabel={t('Фонарик')} style={{ width: 48, height: 46, alignItems: 'center', justifyContent: 'center' }}>
                <Icon name={torch ? 'flash' : 'flash-outline'} size={21} color="#fff" />
              </Pressable>
            ) : null}
          </View>
        </Animated.View>
      ) : null}

      {!recording && sel.end > sel.start ? (
        <View style={{ position: 'absolute', left: 10, bottom: '100%', marginBottom: 6, flexDirection: 'row', backgroundColor: c.card, borderRadius: 13, padding: 4, gap: 2,
          shadowColor: '#000', shadowOpacity: 0.25, shadowRadius: 10, shadowOffset: { width: 0, height: 3 }, elevation: 6 }}>
          {([['**', 'Ж', { fontWeight: '800' }], ['__', 'К', { fontStyle: 'italic' }], ['~~', 'З', { textDecorationLine: 'line-through' }], ['`', 'M', { fontFamily: 'monospace' }]] as const).map(([mark, label, st]) => (
            <Pressable key={mark} onPress={() => format(mark)} style={{ minWidth: 38, height: 36, alignItems: 'center', justifyContent: 'center', borderRadius: 9 }}>
              <Text style={[{ color: c.ink, fontSize: 15 }, st]}>{label}</Text>
            </Pressable>
          ))}
          <Pressable onPress={() => format('||')} style={{ height: 36, paddingHorizontal: 10, alignItems: 'center', justifyContent: 'center', borderRadius: 9 }}>
            <Text style={{ color: c.ink, fontSize: 14 }}>▒ {t('Скрытый')}</Text>
          </Pressable>
        </View>
      ) : null}
      {banner && !recording ? (
        <Animated.View entering={FadeInDown.duration(160)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingLeft: 14, paddingRight: 6, paddingTop: 7, paddingBottom: 2,
          backgroundColor: c.card, borderTopWidth: 0.5, borderTopColor: c.line }}>
          <Icon name={banner.kind === 'edit' ? 'pencil' : 'arrow-undo'} size={21} color={c.accent} />
          <View style={{ flex: 1, borderLeftWidth: 3, borderLeftColor: c.accent, paddingLeft: 9 }}>
            <Text style={{ color: c.accent, fontSize: 13.5, fontWeight: '700' }} numberOfLines={1}>{banner.title}</Text>
            <Text style={{ color: c.inkSoft, fontSize: 14 }} numberOfLines={1}>{banner.text}</Text>
          </View>
          <Pressable onPress={onBannerClose} hitSlop={10} accessibilityLabel={t('Отмена')} style={{ width: 36, height: 36, alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="close" size={20} color={c.inkSoft} />
          </Pressable>
        </Animated.View>
      ) : null}
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8, paddingHorizontal: 8, paddingVertical: 7, backgroundColor: c.card, borderTopWidth: banner && !recording ? 0 : 0.5, borderTopColor: c.line }}>
        {recording ? (
          <Animated.View entering={FadeIn.duration(150)} style={{ flex: 1, height: 46, flexDirection: 'row', alignItems: 'center', gap: 9, paddingLeft: 10 }}>
            <RecDot color={c.bad} still={!!rec?.pausedAt} />
            <Text style={{ color: c.ink, fontSize: 16, minWidth: 62, fontVariant: ['tabular-nums'] }}>{clock(sec)}</Text>
            {rec?.locked ? (
              <Pressable onPress={() => finish(false)} hitSlop={10} accessibilityLabel={t('Отменить запись')} style={{ flex: 1, alignItems: 'center' }}>
                <Text style={{ color: c.accent, fontSize: 14.5, fontWeight: '800', letterSpacing: 0.6 }}>{t('Отмена').toUpperCase()}</Text>
              </Pressable>
            ) : (
              <Animated.View style={[{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 3 }, slideStyle]}>
                <Icon name="chevron-back" size={17} color={c.inkSoft} />
                <Text style={{ color: c.inkSoft, fontSize: 15 }} numberOfLines={1}>{t('Влево — отмена')}</Text>
              </Animated.View>
            )}
          </Animated.View>
        ) : (
          <View style={{ flex: 1, flexDirection: 'row', alignItems: 'flex-end', minHeight: 46, backgroundColor: c.card2, borderRadius: 23,
            borderWidth: 1, borderColor: c.line, paddingLeft: 16, paddingRight: onAttach ? 2 : 12 }}>
            <TextInput ref={field} value={text} onChangeText={setText} onSelectionChange={(e) => setSel(e.nativeEvent.selection)} placeholder={t('Сообщение')} placeholderTextColor={c.inkSoft} multiline maxLength={2000}
              {...(Platform.OS === 'web' ? { rows: 1 } : {})}
              style={{ flex: 1, maxHeight: 120, paddingTop: Platform.OS === 'ios' ? 12 : 9, paddingBottom: Platform.OS === 'ios' ? 12 : 9, fontSize: 16, lineHeight: 21, color: c.ink }} />
            {onAttach ? (
              <Pressable onPress={onAttach} disabled={busy} hitSlop={6} accessibilityLabel={t('Отправить файл')}
                style={{ width: 42, height: 44, alignItems: 'center', justifyContent: 'center' }}>
                {busy ? <ActivityIndicator color={c.accent} /> : <Icon name="attach" size={25} color={c.inkSoft} style={{ transform: [{ rotate: '35deg' }] }} />}
              </Pressable>
            ) : null}
          </View>
        )}

        {showSend ? (
          <Animated.View key="send" entering={ZoomIn.duration(140)} exiting={ZoomOut.duration(100)}>
            <Pressable onPress={() => sendText()} onLongPress={menu} delayLongPress={400} disabled={!text.trim()}
              accessibilityLabel={t('Отправить')} accessibilityHint={t('Долгое нажатие — без звука или по расписанию')}
              style={[round, shadow, { backgroundColor: text.trim() ? c.accent : c.line }]}>
              <Icon name={banner?.kind === 'edit' ? 'checkmark' : 'send'} size={banner?.kind === 'edit' ? 24 : 20} color="#fff" />
            </Pressable>
          </Animated.View>
        ) : canRecord ? (
          <View style={{ width: 46, height: 46 }}>
            {recording && !rec?.locked ? (
              // «замок»: потяни вверх — запись без рук
              // появление — на внешнем слое, движение за пальцем — на внутреннем (иначе Reanimated ругается: одно перебивает другое)
              <Animated.View entering={FadeInDown.duration(200)} style={{ position: 'absolute', bottom: 126, left: -16 }}>
                <Animated.View style={[floating, { position: 'relative', width: 42, paddingTop: 11, paddingBottom: 8, borderRadius: 21, gap: 3 }, lockStyle]}>
                  <Icon name="lock-closed" size={18} color={c.inkSoft} />
                  <Animated.View style={arrowStyle}><Icon name="chevron-up" size={15} color={c.inkSoft} /></Animated.View>
                </Animated.View>
              </Animated.View>
            ) : null}
            {rec?.locked && rec.kind === 'voice' ? (
              <Animated.View entering={ZoomIn.duration(160)} style={[floating, { bottom: 78, left: -4, width: 42, height: 42, borderRadius: 21 }]}>
                <Pressable onPress={togglePause} hitSlop={8} accessibilityLabel={rec.pausedAt ? t('Продолжить запись') : t('Пауза')}
                  style={{ width: 42, height: 42, alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name={rec.pausedAt ? 'mic' : 'pause'} size={20} color={rec.pausedAt ? c.bad : c.inkSoft} />
                </Pressable>
              </Animated.View>
            ) : null}
            <GestureDetector gesture={gesture}>
              <Animated.View style={[{ width: 46, height: 46 }, btnStyle]}
                accessible accessibilityRole="button"
                accessibilityLabel={rec?.locked ? t('Отправить') : mode === 'voice' ? t('Голосовое сообщение') : t('Видеокружок')}
                accessibilityHint={t('Нажмите — голос или кружок. Удерживайте — записать: отпустите — отправить, влево — отмена, вверх — без рук')}>
                {recording && !rec?.locked && !rec?.pausedAt ? (
                  <>
                    <Animated.View pointerEvents="none" style={[{ position: 'absolute', width: 46, height: 46, borderRadius: 23, backgroundColor: c.accent }, wave2]} />
                    <Animated.View pointerEvents="none" style={[{ position: 'absolute', width: 46, height: 46, borderRadius: 23, backgroundColor: c.accent }, wave1]} />
                  </>
                ) : null}
                <View style={[round, shadow, { backgroundColor: c.accent }]}>
                  <Icon name={rec?.locked ? 'send' : (rec?.kind ?? mode) === 'voice' ? 'mic' : 'aperture-outline'} size={rec?.locked ? 18 : 22} color="#fff" />
                </View>
              </Animated.View>
            </GestureDetector>
          </View>
        ) : null}
      </View>

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

function RecDot({ color, still }: { color: string; still?: boolean }) {
  const o = useSharedValue(1);
  useEffect(() => {
    o.value = still ? 0.35 : withRepeat(withTiming(0.25, { duration: 550 }), -1, true);
  }, [o, still]);
  const style = useAnimatedStyle(() => ({ opacity: o.value }));
  return <Animated.View style={[{ width: 11, height: 11, borderRadius: 6, backgroundColor: color }, style]} />;
}
