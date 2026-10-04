/**
 * Профиль «как в Telegram»: большой аватар по центру, имя и «в сети», ряд круглых кнопок,
 * карточка сведений (телефон, @имя, о себе, соцсети). Общий для своей вкладки и страницы человека.
 */
import * as Clipboard from 'expo-clipboard';
import * as Haptics from 'expo-haptics';
import { useState, type ReactNode } from 'react';
import { Alert, Linking, Pressable, View } from 'react-native';

import { useApp, type Privacy, type SocialLink } from '@/state/app';

import { Avatar, Icon, Press, Sheet, Txt, type IconName } from './kit';

export const SOCIAL: { key: string; name: string; icon: IconName; hint: string }[] = [
  { key: 'telegram', name: 'Telegram', icon: 'paper-plane-outline', hint: 'username' },
  { key: 'instagram', name: 'Instagram', icon: 'logo-instagram', hint: 'username' },
  { key: 'youtube', name: 'YouTube', icon: 'logo-youtube', hint: 'channel' },
  { key: 'tiktok', name: 'TikTok', icon: 'logo-tiktok', hint: 'username' },
  { key: 'whatsapp', name: 'WhatsApp', icon: 'logo-whatsapp', hint: '+998 90 123 45 67' },
  { key: 'facebook', name: 'Facebook', icon: 'logo-facebook', hint: 'username' },
  { key: 'x', name: 'X (Twitter)', icon: 'logo-twitter', hint: 'username' },
  { key: 'vk', name: 'VK', icon: 'logo-vk', hint: 'username' },
  { key: 'github', name: 'GitHub', icon: 'logo-github', hint: 'username' },
  { key: 'discord', name: 'Discord', icon: 'logo-discord', hint: 'name#0000' },
  { key: 'linkedin', name: 'LinkedIn', icon: 'logo-linkedin', hint: 'username' },
  { key: 'website', name: 'Сайт', icon: 'globe-outline', hint: 'example.com' },
  { key: 'other', name: 'Другое', icon: 'link-outline', hint: '' },
];
const SOCIAL_BY = Object.fromEntries(SOCIAL.map((x) => [x.key, x]));

export function privacyName(p: Privacy | undefined, t: (s: string) => string) {
  return p === 'close' ? t('Близкие друзья') : p === 'nobody' ? t('Никто') : t('Все');
}

export function ProfileHead({ name, avatar, hue, status, online, verified, onAvatar, photos, onCamera }: {
  name: string; avatar?: string; hue: number; status: string; online?: boolean; verified?: boolean; onAvatar?: () => void;
  photos?: number; onCamera?: () => void;
}) {
  const { c } = useApp();
  return (
    <View style={{ alignItems: 'center', gap: 4, paddingTop: 4 }}>
      <View>
        <Pressable onPress={onAvatar} disabled={!onAvatar} accessibilityLabel={name}>
          <Avatar uri={avatar} name={name} size={108} hue={hue} />
          {photos && photos > 1 ? (
            <View style={{ position: 'absolute', right: 4, bottom: 4, minWidth: 24, height: 24, paddingHorizontal: 7, borderRadius: 12, backgroundColor: 'rgba(10,12,22,0.62)', alignItems: 'center', justifyContent: 'center' }}>
              <Txt kind="small" color="#fff" style={{ fontWeight: '800', fontSize: 12 }}>{photos}</Txt>
            </View>
          ) : null}
        </Pressable>
        {onCamera ? (
          <Pressable onPress={onCamera} hitSlop={8} style={{ position: 'absolute', right: -2, bottom: -2, width: 38, height: 38, borderRadius: 19, backgroundColor: c.accent,
            alignItems: 'center', justifyContent: 'center', borderWidth: 3, borderColor: c.bg }}>
            <Icon name="camera" size={18} color="#fff" />
          </Pressable>
        ) : null}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, paddingHorizontal: 20 }}>
        <Txt style={{ fontSize: 23, fontWeight: '800', letterSpacing: -0.2, textAlign: 'center', flexShrink: 1 }} numberOfLines={2}>{name}</Txt>
        {verified ? <Icon name="checkmark-circle" size={20} color={c.accent} /> : null}
      </View>
      {status ? <Txt color={online ? c.accent : c.inkSoft} style={{ fontSize: 14.5, fontWeight: online ? '600' : '400' }}>{status}</Txt> : null}
    </View>
  );
}

export type Action = { icon: IconName; label: string; onPress: () => void; off?: boolean };

/** Ряд кнопок под именем: Чат · Звук · Звонок · Видео. */
export function ProfileActions({ items }: { items: Action[] }) {
  const { c, dark } = useApp();
  return (
    <View style={{ flexDirection: 'row', gap: 8 }}>
      {items.map((a) => (
        <Press key={a.label} onPress={a.onPress} haptic scale={0.95} style={{ flex: 1, minHeight: 62, borderRadius: 16, backgroundColor: c.card, alignItems: 'center', justifyContent: 'center', gap: 5,
          paddingVertical: 9, paddingHorizontal: 4, ...(dark ? {} : { shadowColor: '#15172a', shadowOpacity: 0.06, shadowRadius: 8, shadowOffset: { width: 0, height: 2 }, elevation: 1 }) }}>
          <Icon name={a.icon} size={22} color={a.off ? c.inkSoft : c.accent} />
          <Txt kind="small" color={a.off ? c.inkSoft : c.accent} style={{ fontWeight: '700', fontSize: 12.5 }} numberOfLines={1}>{a.label}</Txt>
        </Press>
      ))}
    </View>
  );
}

function InfoRow({ icon, value, label, onPress, first, accent }: { icon: IconName; value: string; label: string; onPress?: () => void; first?: boolean; accent?: boolean }) {
  const { c } = useApp();
  return (
    <Pressable onPress={onPress} disabled={!onPress} style={({ pressed }) => ({ flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 10, paddingHorizontal: 16,
      borderTopWidth: first ? 0 : 0.5, borderTopColor: c.line, backgroundColor: pressed ? c.card2 : 'transparent' })}>
      <Icon name={icon} size={21} color={c.inkSoft} />
      <View style={{ flex: 1 }}>
        <Txt style={{ fontSize: 15.5, fontWeight: '600' }} color={accent ? c.accent : c.ink}>{value}</Txt>
        <Txt kind="small" style={{ fontSize: 12.5 }}>{label}</Txt>
      </View>
    </Pressable>
  );
}

function LinkPills({ first, links, open, copy }: { first: boolean; links: SocialLink[]; open: (l: SocialLink) => void; copy: (text: string) => void }) {
  const { c, t } = useApp();
  const [all, setAll] = useState(false);
  const MAX = 4;
  const pill = (l: SocialLink, i: number) => (
    <Pressable key={i} onPress={() => open(l)} onLongPress={() => copy(l.show || l.value)} accessibilityLabel={`${l.title}: ${l.show || l.value}`}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 7, height: 34, paddingLeft: 10, paddingRight: 13, borderRadius: 17, backgroundColor: c.card2,
        borderWidth: 0.5, borderColor: c.line, maxWidth: '100%', opacity: l.privacy === 'nobody' ? 0.45 : 1 }}>
      <Icon name={SOCIAL_BY[l.kind]?.icon ?? 'link-outline'} size={17} color={c.accent} />
      <Txt numberOfLines={1} style={{ fontSize: 14, fontWeight: '600', maxWidth: 150 }}>{l.show || l.value}</Txt>
    </Pressable>
  );
  return (
    <View style={{ paddingVertical: 12, paddingHorizontal: 16, borderTopWidth: first ? 0 : 0.5, borderTopColor: c.line }}>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {links.slice(0, MAX).map(pill)}
        {links.length > MAX ? (
          <Pressable onPress={() => setAll(true)} style={{ height: 34, paddingHorizontal: 13, borderRadius: 17, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
            <Txt style={{ fontSize: 14, fontWeight: '700', color: c.accent }}>{t('ещё {n}', { n: links.length - MAX })}</Txt>
          </Pressable>
        ) : null}
      </View>
      <Sheet open={all} onClose={() => setAll(false)} title={t('Соцсети и ссылки')}
        items={links.map((l) => ({ title: l.show || l.value, subtitle: l.title || SOCIAL_BY[l.kind]?.name || '', icon: SOCIAL_BY[l.kind]?.icon ?? 'link-outline',
          onPress: () => { setAll(false); open(l); } }))} />
    </View>
  );
}

/** Карточка сведений. mine — свой профиль: рядом с подписью видно, кому это показывается. */
export function ProfileInfo({ phone, handle, bio, city, links, linksView, joined, mine, phonePrivacy, onSetHandle }: {
  phone?: string; handle?: string; bio?: string; city?: string; links?: SocialLink[]; linksView?: string; joined?: string; mine?: boolean;
  phonePrivacy?: Privacy; onSetHandle?: () => void;
}) {
  const { c, t, dark } = useApp();
  const copy = async (text: string) => {
    await Clipboard.setStringAsync(text);
    Haptics.selectionAsync().catch(() => {});
    Alert.alert(t('Скопировано'), text);
  };
  const who = (p?: Privacy) => (mine ? ` · ${p === 'close' ? t('видят близкие друзья') : p === 'nobody' ? t('никто не видит') : t('видят все')}` : '');
  const rows: ReactNode[] = [];
  const add = (key: string, node: (first: boolean) => ReactNode) => rows.push(<View key={key}>{node(rows.length === 0)}</View>);
  if (phone) add('phone', (f) => <InfoRow first={f} icon="call-outline" value={phone} label={t('Телефон') + who(phonePrivacy)} onPress={mine ? undefined : () => Linking.openURL(`tel:${phone.replace(/[^+\d]/g, '')}`)} />);
  if (handle) add('handle', (f) => <InfoRow first={f} icon="at-outline" value={`@${handle}`} label={t('Имя пользователя')} onPress={() => copy(`@${handle}`)} />);
  else if (mine && onSetHandle) add('handle', (f) => <InfoRow first={f} accent icon="at-outline" value={t('Задать имя пользователя')} label={t('Чтобы вас находили в поиске и писали вам, не зная номера')} onPress={onSetHandle} />);
  if (bio) add('bio', (f) => <InfoRow first={f} icon="information-circle-outline" value={bio} label={t('О себе')} />);
  if (city) add('city', (f) => <InfoRow first={f} icon="location-outline" value={city} label={t('Город')} />);
  const openLink = (l: SocialLink) => (l.url ? Linking.openURL(l.url).catch(() => copy(l.value)) : copy(l.value));
  if (linksView === 'pills' && links?.length) {
    // пилюли «значок + имя»: видны первые четыре, остальные — за «ещё N» (так делает Instagram)
    add('links', (f) => <LinkPills first={f} links={links} open={openLink} copy={copy} />);
  } else if (linksView === 'icons' && links?.length) {
    // много ссылок не растягивают профиль: значки сетей в ряд, нажатие открывает, долгое — копирует
    add('links', (f) => (
      <View style={{ paddingVertical: 12, paddingHorizontal: 16, gap: 8, borderTopWidth: f ? 0 : 0.5, borderTopColor: c.line }}>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
          {links.map((l, i) => (
            <Pressable key={i} onPress={() => openLink(l)} onLongPress={() => copy(l.show || l.value)} accessibilityLabel={`${l.title}: ${l.show || l.value}`}
              style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: c.card2, alignItems: 'center', justifyContent: 'center', opacity: l.privacy === 'nobody' ? 0.45 : 1 }}>
              <Icon name={SOCIAL_BY[l.kind]?.icon ?? 'link-outline'} size={21} color={c.accent} />
            </Pressable>
          ))}
        </View>
        <Txt kind="small">{t('Соцсети и ссылки')}</Txt>
      </View>
    ));
  } else {
    (links ?? []).forEach((l, i) => add(`l${i}`, (f) => (
      <InfoRow first={f} icon={SOCIAL_BY[l.kind]?.icon ?? 'link-outline'} value={l.show || l.value} label={(l.title || SOCIAL_BY[l.kind]?.name || '') + who(l.privacy)}
        onPress={() => openLink(l)} />
    )));
  }
  if (joined) add('joined', (f) => <InfoRow first={f} icon="calendar-outline" value={joined} label={t('на ilm4 с')} />);
  if (!rows.length) return null;
  return (
    <View style={{ backgroundColor: c.card, borderRadius: 20, overflow: 'hidden', paddingVertical: 2,
      ...(dark ? {} : { shadowColor: '#15172a', shadowOpacity: 0.06, shadowRadius: 10, shadowOffset: { width: 0, height: 3 }, elevation: 1 }) }}>
      {rows}
    </View>
  );
}
