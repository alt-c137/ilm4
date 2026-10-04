/** Общие элементы интерфейса в стиле ilm4. */
import Ionicons from '@expo/vector-icons/Ionicons';
import * as Haptics from 'expo-haptics';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { createContext, useContext, useEffect, useState, type ComponentProps, type ReactNode } from 'react';
import {
  ActivityIndicator, Modal, Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View,
  type StyleProp, type TextInputProps, type TextStyle, type ViewStyle,
} from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withRepeat, withSpring, withTiming } from 'react-native-reanimated';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

import { radius } from '@/lib/theme';
import { useApp } from '@/state/app';

export type IconName = ComponentProps<typeof Ionicons>['name'];

export function Icon({ name, size = 22, color, style }: { name: IconName; size?: number; color?: string; style?: any }) {
  const { c } = useApp();
  return <Ionicons name={name} size={size} color={color ?? c.ink} style={style} />;
}

type TxtKind = 'h1' | 'h2' | 'h3' | 'body' | 'small' | 'label' | 'muted';
export function Txt({ kind = 'body', style, children, color, numberOfLines, selectable }: {
  kind?: TxtKind; style?: StyleProp<TextStyle>; children: ReactNode; color?: string; numberOfLines?: number; selectable?: boolean;
}) {
  const { c } = useApp();
  const base: Record<TxtKind, TextStyle> = {
    h1: { fontSize: 26, fontWeight: '800', letterSpacing: -0.4, color: c.ink },
    h2: { fontSize: 20, fontWeight: '800', letterSpacing: -0.2, color: c.ink },
    h3: { fontSize: 16, fontWeight: '700', color: c.ink },
    body: { fontSize: 15, lineHeight: 21, color: c.ink },
    small: { fontSize: 13, lineHeight: 18, color: c.inkSoft },
    label: { fontSize: 12, fontWeight: '700', letterSpacing: 0.6, textTransform: 'uppercase', color: c.inkSoft },
    muted: { fontSize: 14, lineHeight: 20, color: c.inkSoft },
  };
  return (
    <Text style={[base[kind], color ? { color } : null, style]} numberOfLines={numberOfLines} selectable={selectable}>
      {children}
    </Text>
  );
}

export function OfflineBar() {
  const { online, c, t } = useApp();
  if (online) return null;
  return (
    <View style={{ backgroundColor: c.warn, paddingVertical: 6, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
      <Icon name="cloud-offline-outline" size={16} color="#fff" />
      <Text style={{ color: '#fff', fontSize: 13, fontWeight: '600' }}>{t('Нет интернета — показано сохранённое')}</Text>
    </View>
  );
}

/** Экран показан как вкладка (нижняя кнопка): стрелка «назад» не нужна. */
export const TabMode = createContext(false);

/** Экран: безопасные отступы, заголовок, прокрутка, «потяни, чтобы обновить». */
export function Screen({ title, back = false, right, children, scroll = true, onRefresh, refreshing = false, padded = true, edges }: {
  title?: string; back?: boolean; right?: ReactNode; children: ReactNode; scroll?: boolean;
  onRefresh?: () => void; refreshing?: boolean; padded?: boolean; edges?: ('top' | 'bottom')[];
}) {
  const { c } = useApp();
  const inTab = useContext(TabMode);
  if (inTab) back = false;
  const body = scroll ? (
    <ScrollView
      contentContainerStyle={[padded && { padding: 16, paddingBottom: 40 }, { gap: 14 }]}
      keyboardShouldPersistTaps="handled"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={c.accent} /> : undefined}>
      {children}
    </ScrollView>
  ) : <View style={[{ flex: 1 }, padded && { padding: 16 }]}>{children}</View>;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={edges ?? ['top']}>
      <OfflineBar />
      {(title || back) && (
        <View style={s.header}>
          {back && (
            <Pressable onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} hitSlop={12} style={s.back}
              accessibilityRole="button" accessibilityLabel="back">
              <Icon name="chevron-back" size={26} color={c.accent} />
            </Pressable>
          )}
          <Txt kind={back ? 'h3' : 'h1'} style={{ flex: 1 }} numberOfLines={1}>{title ?? ''}</Txt>
          {right}
        </View>
      )}
      {body}
    </SafeAreaView>
  );
}

const APressable = Animated.createAnimatedComponent(Pressable);

/**
 * Нажимаемый элемент с «живым» откликом: слегка проседает под пальцем и пружинит обратно.
 * Анимация идёт в отдельном потоке интерфейса (Reanimated) — не подтормаживает, даже когда приложение занято.
 */
export function Press({ children, style, onPress, onLongPress, disabled, scale = 0.97, haptic, hitSlop, accessibilityRole }: {
  children: ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void; onLongPress?: () => void; disabled?: boolean;
  scale?: number; haptic?: boolean; hitSlop?: number; accessibilityRole?: 'button' | 'link' | 'tab';
}) {
  const v = useSharedValue(1);
  const anim = useAnimatedStyle(() => ({ transform: [{ scale: v.get() }] }));
  return (
    <APressable
      disabled={disabled} hitSlop={hitSlop} accessibilityRole={accessibilityRole} onLongPress={onLongPress}
      onPress={() => { if (haptic) Haptics.selectionAsync().catch(() => {}); onPress?.(); }}
      onPressIn={() => v.set(withTiming(scale, { duration: 90 }))}
      onPressOut={() => v.set(withSpring(1, { damping: 14, stiffness: 260 }))}
      style={[style, anim]}>
      {children}
    </APressable>
  );
}

/** Заглушка на время загрузки списка: серые «карточки» мягко мерцают — понятно, что данные идут. */
export function Skeleton({ rows = 6, image = false }: { rows?: number; image?: boolean }) {
  const { c } = useApp();
  const o = useSharedValue(0.45);
  useEffect(() => {
    o.set(withRepeat(withTiming(1, { duration: 750 }), -1, true));
  }, [o]);
  const anim = useAnimatedStyle(() => ({ opacity: o.get() }));
  return (
    <Animated.View style={[{ gap: 10 }, anim]}>
      {Array.from({ length: rows }, (_x, i) => (
        <View key={i} style={{ flexDirection: 'row', gap: 12, backgroundColor: c.card, borderRadius: 20, padding: 12 }}>
          {image ? <View style={{ width: 84, height: 84, borderRadius: 14, backgroundColor: c.card2 }} /> : null}
          <View style={{ flex: 1, gap: 9, justifyContent: 'center', paddingVertical: image ? 0 : 6 }}>
            <View style={{ height: 15, width: `${72 - (i % 3) * 12}%`, borderRadius: 6, backgroundColor: c.card2 }} />
            <View style={{ height: 12, width: `${48 + (i % 2) * 14}%`, borderRadius: 6, backgroundColor: c.card2 }} />
            <View style={{ height: 10, width: '26%', borderRadius: 6, backgroundColor: c.card2 }} />
          </View>
        </View>
      ))}
    </Animated.View>
  );
}

export function Card({ children, style, onPress, soft }: { children: ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void; soft?: boolean }) {
  const { c, dark } = useApp();
  const st = [{
    backgroundColor: soft ? c.card2 : c.card, borderRadius: radius.l, padding: 16,
    ...(dark || soft ? {} : { shadowColor: '#15172a', shadowOpacity: 0.06, shadowRadius: 10, shadowOffset: { width: 0, height: 3 }, elevation: 1 }),
  }, style];
  if (!onPress) return <View style={st}>{children}</View>;
  return <Press onPress={onPress} scale={0.98} style={st}>{children}</Press>;
}

export function Button({ title, onPress, kind = 'primary', icon, loading, disabled, style, small, color }: {
  title: string; onPress?: () => void; kind?: 'primary' | 'ghost' | 'soft' | 'danger'; icon?: IconName;
  loading?: boolean; disabled?: boolean; style?: StyleProp<ViewStyle>; small?: boolean; color?: string;
}) {
  const { c } = useApp();
  const bg = { primary: c.accent, ghost: 'transparent', soft: c.accentSoft, danger: c.bad }[kind];
  const fg = color ?? { primary: c.onAccent, ghost: c.accent, soft: c.accentD, danger: '#fff' }[kind];
  return (
    <Press
      onPress={onPress} disabled={disabled || loading} accessibilityRole="button" scale={0.96} haptic={kind === 'primary'}
      style={[{
        backgroundColor: bg, borderRadius: radius.pill, paddingVertical: small ? 9 : 14, paddingHorizontal: small ? 14 : 20,
        flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
        borderWidth: kind === 'ghost' ? 1.5 : 0, borderColor: color ?? c.accent, opacity: disabled ? 0.5 : 1,
      }, style]}>
      {loading ? <ActivityIndicator color={fg} /> : icon ? <Icon name={icon} size={small ? 16 : 19} color={fg} /> : null}
      <Text style={{ color: fg, fontWeight: '700', fontSize: small ? 14 : 16, flexShrink: 1 }} numberOfLines={1} adjustsFontSizeToFit>{title}</Text>
    </Press>
  );
}

export function Field({ label, error, style, ...props }: TextInputProps & { label?: string; error?: string }) {
  const { c } = useApp();
  return (
    <View style={{ gap: 6 }}>
      {label ? <Txt kind="small" style={{ fontWeight: '600', color: c.ink }}>{label}</Txt> : null}
      <TextInput
        placeholderTextColor={c.inkSoft}
        {...props}
        style={[{
          backgroundColor: c.card2, borderRadius: radius.m, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16,
          color: c.ink, borderWidth: 1, borderColor: error ? c.bad : c.line,
        }, props.multiline && { minHeight: 110, textAlignVertical: 'top' }, style]}
      />
      {error ? <Txt kind="small" color={c.bad}>{error}</Txt> : null}
    </View>
  );
}

export function Chip({ label, on, onPress, icon }: { label: string; on?: boolean; onPress?: () => void; icon?: IconName }) {
  const { c } = useApp();
  return (
    <Press onPress={onPress} scale={0.94} haptic style={{
      flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8, paddingHorizontal: 14, borderRadius: radius.pill,
      backgroundColor: on ? c.accent : c.card, borderWidth: 1, borderColor: on ? c.accent : c.line,
    }}>
      {icon ? <Icon name={icon} size={15} color={on ? '#fff' : c.inkSoft} /> : null}
      <Text style={{ color: on ? '#fff' : c.ink, fontWeight: '600', fontSize: 14 }}>{label}</Text>
    </Press>
  );
}

export function Segmented<T extends string>({ value, options, onChange }: { value: T; options: { key: T; label: string }[]; onChange: (v: T) => void }) {
  const { c } = useApp();
  return (
    <View style={{ flexDirection: 'row', backgroundColor: c.card2, borderRadius: radius.pill, padding: 4, borderWidth: 1, borderColor: c.line }}>
      {options.map((o) => (
        <Pressable key={o.key} onPress={() => onChange(o.key)} style={{
          flex: 1, paddingVertical: 9, borderRadius: radius.pill, alignItems: 'center',
          backgroundColor: value === o.key ? c.card : 'transparent',
          ...(value === o.key ? { shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 4, elevation: 1 } : {}),
        }}>
          <Text style={{ fontWeight: '700', fontSize: 14, color: value === o.key ? c.ink : c.inkSoft }} numberOfLines={1}>{o.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export function Row({ icon, title, subtitle, onPress, right, danger }: {
  icon?: IconName; title: string; subtitle?: string; onPress?: () => void; right?: ReactNode; danger?: boolean;
}) {
  const { c } = useApp();
  return (
    <Pressable onPress={onPress} disabled={!onPress} style={({ pressed }) => [{
      flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 13, opacity: pressed ? 0.6 : 1,
    }]}>
      {icon ? (
        <View style={{ width: 36, height: 36, borderRadius: 11, backgroundColor: danger ? '#fdecec' : c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
          <Icon name={icon} size={19} color={danger ? c.bad : c.accentD} />
        </View>
      ) : null}
      <View style={{ flex: 1 }}>
        <Txt kind="h3" color={danger ? c.bad : undefined} style={{ fontWeight: '600' }}>{title}</Txt>
        {subtitle ? <Txt kind="small" numberOfLines={2}>{subtitle}</Txt> : null}
      </View>
      {right ?? (onPress ? <Icon name="chevron-forward" size={18} color={c.inkSoft} /> : null)}
    </Pressable>
  );
}

/** Строка настроек как в Telegram: цветной значок, название, справа — текущее значение и стрелка. */
export function SetRow({ tint, icon, title, subtitle, value, onPress, danger }: {
  tint: string; icon: IconName; title: string; subtitle?: string; value?: string; onPress?: () => void; danger?: boolean;
}) {
  const { c } = useApp();
  return (
    <Pressable onPress={onPress} disabled={!onPress} style={({ pressed }) => ({ flexDirection: 'row', alignItems: 'center', gap: 13, paddingVertical: 10, opacity: pressed ? 0.6 : 1 })}>
      <View style={{ width: 32, height: 32, borderRadius: 9, backgroundColor: tint, alignItems: 'center', justifyContent: 'center' }}>
        <Icon name={icon} size={18} color="#fff" />
      </View>
      <View style={{ flex: 1 }}>
        <Txt color={danger ? c.bad : undefined} style={{ fontSize: 16, fontWeight: '600' }} numberOfLines={1}>{title}</Txt>
        {subtitle ? <Txt kind="small" numberOfLines={1}>{subtitle}</Txt> : null}
      </View>
      {value ? <Txt kind="muted" numberOfLines={1} style={{ maxWidth: 150, fontSize: 15 }}>{value}</Txt> : null}
      {onPress ? <Icon name="chevron-forward" size={17} color={c.inkSoft} /> : null}
    </Pressable>
  );
}

/** Блок строк настроек: карточка, между строками — тонкая линия с отступом под значок. */
export function SetGroup({ title, hint, children }: { title?: string; hint?: string; children: ReactNode }) {
  const { c } = useApp();
  const rows = (Array.isArray(children) ? children.flat() : [children]).filter(Boolean);
  return (
    <View style={{ gap: 7 }}>
      {title ? <Txt kind="label" style={{ paddingHorizontal: 6 }}>{title}</Txt> : null}
      <Card style={{ paddingVertical: 3 }}>
        {rows.map((row, i) => (
          <View key={i}>
            {i ? <View style={{ height: StyleSheet.hairlineWidth, backgroundColor: c.line, marginLeft: 45 }} /> : null}
            {row}
          </View>
        ))}
      </Card>
      {hint ? <Txt kind="small" style={{ paddingHorizontal: 6 }}>{hint}</Txt> : null}
    </View>
  );
}

export function Divider() {
  const { c } = useApp();
  return <View style={{ height: StyleSheet.hairlineWidth, backgroundColor: c.line }} />;
}

export function Loading({ label }: { label?: string }) {
  const { c } = useApp();
  return (
    <View style={{ padding: 40, alignItems: 'center', gap: 12 }}>
      <ActivityIndicator color={c.accent} size="large" />
      {label ? <Txt kind="muted">{label}</Txt> : null}
    </View>
  );
}

export function Empty({ icon = 'leaf-outline', title, text, action }: { icon?: IconName; title: string; text?: string; action?: ReactNode }) {
  const { c } = useApp();
  return (
    <View style={{ alignItems: 'center', padding: 32, gap: 10 }}>
      <View style={{ width: 64, height: 64, borderRadius: 22, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
        <Icon name={icon} size={30} color={c.accent} />
      </View>
      <Txt kind="h3" style={{ textAlign: 'center' }}>{title}</Txt>
      {text ? <Txt kind="muted" style={{ textAlign: 'center' }}>{text}</Txt> : null}
      {action}
    </View>
  );
}

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  const { t } = useApp();
  return <Empty icon="alert-circle-outline" title={error} action={onRetry ? <Button small kind="soft" title={t('Повторить')} onPress={onRetry} /> : null} />;
}

export function Avatar({ uri, name, size = 44, hue = 0, online }: { uri?: string; name: string; size?: number; hue?: number; online?: boolean }) {
  const { c } = useApp();
  const colors = ['#6d5efc', '#0ea5e9', '#10b981', '#f97316', '#ec4899', '#8b5cf6', '#14b8a6'];
  const font = Math.round(size * 0.4);
  const face = uri ? <Image source={{ uri }} style={{ width: size, height: size, borderRadius: size / 2 }} contentFit="cover" /> : (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: colors[Math.abs(hue) % colors.length], alignItems: 'center', justifyContent: 'center' }}>
      {/* высота строки и отступы шрифта заданы явно — иначе на Android буква уезжает вверх */}
      <Text allowFontScaling={false} style={{ color: '#fff', fontWeight: '800', fontSize: font, lineHeight: Math.round(font * 1.22), textAlign: 'center',
        includeFontPadding: false, textAlignVertical: 'center' }}>{(name || '?').trim().slice(0, 1).toUpperCase()}</Text>
    </View>
  );
  if (!online) return face;
  const dot = Math.max(11, Math.round(size * 0.26));
  return (
    <View style={{ width: size, height: size }}>
      {face}
      <View style={{ position: 'absolute', right: 0, bottom: 0, width: dot, height: dot, borderRadius: dot / 2, backgroundColor: '#2fc55e', borderWidth: 2.5, borderColor: c.card }} />
    </View>
  );
}

export function Badge({ n }: { n: number }) {
  const { c } = useApp();
  if (!n) return null;
  return (
    <View style={{ minWidth: 20, height: 20, borderRadius: 10, backgroundColor: c.bad, paddingHorizontal: 6, alignItems: 'center', justifyContent: 'center' }}>
      <Text style={{ color: '#fff', fontSize: 12, fontWeight: '800' }}>{n > 99 ? '99+' : n}</Text>
    </View>
  );
}

export type SheetItem = { title: string; subtitle?: string; icon?: IconName; danger?: boolean; on?: boolean; onPress: () => void };

/** Меню снизу экрана (как в Telegram): сколько угодно пунктов — системное окно Android вмещает только три. */
export function Sheet({ open, onClose, title, items, header }: { open: boolean; onClose: () => void; title?: string; items: SheetItem[]; header?: ReactNode }) {
  const { c } = useApp();
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={open} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <Pressable style={{ flex: 1, backgroundColor: c.overlay }} onPress={onClose} accessibilityLabel="close" />
      <View style={{ backgroundColor: c.card, borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingTop: 8, paddingBottom: 10 + insets.bottom, maxHeight: '75%' }}>
        <View style={{ alignSelf: 'center', width: 38, height: 4, borderRadius: 2, backgroundColor: c.line, marginBottom: 6 }} />
        {title ? <Txt kind="label" style={{ paddingHorizontal: 20, paddingVertical: 6 }}>{title}</Txt> : null}
        {header}
        <ScrollView>
          {items.map((it) => (
            <Pressable key={it.title} onPress={() => { onClose(); it.onPress(); }}
              style={({ pressed }) => ({ flexDirection: 'row', alignItems: 'center', gap: 14, paddingHorizontal: 20, paddingVertical: 13, backgroundColor: pressed ? c.card2 : 'transparent' })}>
              {it.icon ? <Icon name={it.icon} size={22} color={it.danger ? c.bad : c.inkSoft} /> : null}
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 16, color: it.danger ? c.bad : c.ink, fontWeight: it.on ? '700' : '500' }}>{it.title}</Text>
                {it.subtitle ? <Txt kind="small">{it.subtitle}</Txt> : null}
              </View>
              {it.on ? <Icon name="checkmark" size={20} color={c.accent} /> : null}
            </Pressable>
          ))}
        </ScrollView>
      </View>
    </Modal>
  );
}

export function Section({ title, children, action }: { title?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <View style={{ gap: 10 }}>
      {title ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 4 }}>
          <Txt kind="label">{title}</Txt>
          {action}
        </View>
      ) : null}
      {children}
    </View>
  );
}

const s = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 6, minHeight: 48 },
  back: { marginLeft: -6, padding: 2 },
});

// ---------- короткое сообщение внизу экрана (как в Telegram: «Сохранено · Открыть») ----------
type ToastData = { id: number; text: string; action?: { label: string; onPress: () => void } };
let toastListener: ((x: ToastData) => void) | null = null;

export function toast(text: string, action?: ToastData['action']) {
  toastListener?.({ id: Date.now(), text, action });
}

/** Ставится один раз в корне приложения. */
export function ToastHost() {
  const insets = useSafeAreaInsets();
  const [item, setItem] = useState<ToastData | null>(null);
  useEffect(() => {
    toastListener = setItem;
    return () => { toastListener = null; };
  }, []);
  useEffect(() => {
    if (!item) return;
    const timer = setTimeout(() => setItem(null), 3200);
    return () => clearTimeout(timer);
  }, [item]);
  if (!item) return null;
  return (
    <View pointerEvents="box-none" style={{ position: 'absolute', left: 0, right: 0, bottom: insets.bottom + 78, alignItems: 'center', paddingHorizontal: 16 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: 'rgba(24,26,40,0.94)', borderRadius: 14, paddingVertical: 11, paddingHorizontal: 16, maxWidth: 420 }}>
        <Text style={{ color: '#fff', fontSize: 15, flexShrink: 1 }}>{item.text}</Text>
        {item.action ? (
          <Pressable hitSlop={10} onPress={() => { const run = item.action!.onPress; setItem(null); run(); }}>
            <Text style={{ color: '#a5b4fc', fontSize: 15, fontWeight: '700' }}>{item.action.label}</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

// ---------- реклама: короткое объявление с пометкой «Реклама» (apps/core/ads.py) ----------
export type AdData = { id: number; title: string; text: string; button: string; image: string; url: string };

export function AdCard({ ad, onOpen, style }: { ad: AdData; onOpen: (url: string) => void; style?: StyleProp<ViewStyle> }) {
  const { c, t } = useApp();
  return (
    <Pressable onPress={() => onOpen(ad.url)} style={[{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: c.card, padding: 14 }, style]}>
      {ad.image ? <Image source={{ uri: ad.image }} style={{ width: 52, height: 52, borderRadius: 13 }} contentFit="cover" /> : null}
      <View style={{ flex: 1, gap: 1 }}>
        <Text style={{ fontSize: 11, fontWeight: '700', letterSpacing: 0.6, color: c.inkSoft, textTransform: 'uppercase' }}>{t('Реклама')}</Text>
        <Text style={{ fontSize: 15, fontWeight: '700', color: c.ink }} numberOfLines={1}>{ad.title}</Text>
        <Text style={{ fontSize: 13.5, color: c.inkSoft }} numberOfLines={3}>{ad.text}</Text>
      </View>
      <View style={{ backgroundColor: c.accentSoft, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 7 }}>
        <Text style={{ color: c.accentD, fontWeight: '700', fontSize: 13.5 }}>{ad.button}</Text>
      </View>
    </Pressable>
  );
}
