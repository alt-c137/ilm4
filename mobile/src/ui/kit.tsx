/** Общие элементы интерфейса в стиле ilm4. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import type { ComponentProps, ReactNode } from 'react';
import {
  ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View,
  type StyleProp, type TextInputProps, type TextStyle, type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

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

/** Экран: безопасные отступы, заголовок, прокрутка, «потяни, чтобы обновить». */
export function Screen({ title, back = false, right, children, scroll = true, onRefresh, refreshing = false, padded = true, edges }: {
  title?: string; back?: boolean; right?: ReactNode; children: ReactNode; scroll?: boolean;
  onRefresh?: () => void; refreshing?: boolean; padded?: boolean; edges?: ('top' | 'bottom')[];
}) {
  const { c } = useApp();
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

export function Card({ children, style, onPress, soft }: { children: ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void; soft?: boolean }) {
  const { c, dark } = useApp();
  const st = [{
    backgroundColor: soft ? c.card2 : c.card, borderRadius: radius.l, padding: 16,
    ...(dark || soft ? {} : { shadowColor: '#15172a', shadowOpacity: 0.06, shadowRadius: 10, shadowOffset: { width: 0, height: 3 }, elevation: 1 }),
  }, style];
  if (!onPress) return <View style={st}>{children}</View>;
  return <Pressable onPress={onPress} style={({ pressed }) => [st, pressed && { opacity: 0.85, transform: [{ scale: 0.99 }] }]}>{children}</Pressable>;
}

export function Button({ title, onPress, kind = 'primary', icon, loading, disabled, style, small, color }: {
  title: string; onPress?: () => void; kind?: 'primary' | 'ghost' | 'soft' | 'danger'; icon?: IconName;
  loading?: boolean; disabled?: boolean; style?: StyleProp<ViewStyle>; small?: boolean; color?: string;
}) {
  const { c } = useApp();
  const bg = { primary: c.accent, ghost: 'transparent', soft: c.accentSoft, danger: c.bad }[kind];
  const fg = color ?? { primary: c.onAccent, ghost: c.accent, soft: c.accentD, danger: '#fff' }[kind];
  return (
    <Pressable
      onPress={onPress} disabled={disabled || loading} accessibilityRole="button"
      style={({ pressed }) => [{
        backgroundColor: bg, borderRadius: radius.pill, paddingVertical: small ? 9 : 14, paddingHorizontal: small ? 14 : 20,
        flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
        borderWidth: kind === 'ghost' ? 1.5 : 0, borderColor: color ?? c.accent, opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
      }, style]}>
      {loading ? <ActivityIndicator color={fg} /> : icon ? <Icon name={icon} size={small ? 16 : 19} color={fg} /> : null}
      <Text style={{ color: fg, fontWeight: '700', fontSize: small ? 14 : 16, flexShrink: 1 }} numberOfLines={1} adjustsFontSizeToFit>{title}</Text>
    </Pressable>
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
    <Pressable onPress={onPress} style={{
      flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8, paddingHorizontal: 14, borderRadius: radius.pill,
      backgroundColor: on ? c.accent : c.card, borderWidth: 1, borderColor: on ? c.accent : c.line,
    }}>
      {icon ? <Icon name={icon} size={15} color={on ? '#fff' : c.inkSoft} /> : null}
      <Text style={{ color: on ? '#fff' : c.ink, fontWeight: '600', fontSize: 14 }}>{label}</Text>
    </Pressable>
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

export function Avatar({ uri, name, size = 44, hue = 0 }: { uri?: string; name: string; size?: number; hue?: number }) {
  const colors = ['#6d5efc', '#0ea5e9', '#10b981', '#f97316', '#ec4899', '#8b5cf6', '#14b8a6'];
  if (uri) return <Image source={{ uri }} style={{ width: size, height: size, borderRadius: size / 2 }} contentFit="cover" />;
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: colors[Math.abs(hue) % colors.length], alignItems: 'center', justifyContent: 'center' }}>
      <Text style={{ color: '#fff', fontWeight: '800', fontSize: size * 0.4 }}>{(name || '?').slice(0, 1).toUpperCase()}</Text>
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
