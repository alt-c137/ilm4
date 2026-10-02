import * as Haptics from 'expo-haptics';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Pressable, useWindowDimensions, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { interpolate, useAnimatedStyle, useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import { scheduleOnRN } from 'react-native-worklets';

import { api, ApiError } from '@/lib/api';
import { openWeb } from '@/lib/links';
import { load } from '@/lib/storage';
import { useApp } from '@/state/app';
import { Badge, Button, Card, Empty, Icon, Loading, Screen, Txt } from '@/ui/kit';
import { KV, ProfileHead, type NkProfile } from '@/ui/nikah';

type State = {
  profile: (NkProfile & { status: string; active: boolean; premium_until: string | null }) | null;
  published?: boolean; left?: number | null; limit?: number; skipped?: number; badges?: { incoming: number; waiting: number }; balance: number;
};

function filtersQuery(f: Record<string, any>) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) {
    if (Array.isArray(v)) {
      q.set(`${k}_min`, String(v[0]));
      q.set(`${k}_max`, String(v[1]));
    } else if (v === true) q.set(k, '1');
    else if (v) q.set(k, String(v));
  }
  return q.toString();
}

export default function NikahHome() {
  const { c, t, user, config } = useApp();
  const [st, setSt] = useState<State | null>(null);
  const [cards, setCards] = useState<NkProfile[]>([]);
  const [left, setLeft] = useState<number | null>(null);
  const [filtered, setFiltered] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadAll = useCallback(async () => {
    if (!user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const s = await api<State>('/nikah/state/');
      setSt(s);
      if (s.profile) {
        const f = await load<Record<string, any>>('nikah_filters', {});
        setFiltered(Object.keys(f).length > 0);
        const feed = await api(`/nikah/feed/?${filtersQuery(f)}`);
        setCards(feed.items);
        setLeft(feed.left);
      }
      setError('');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useFocusEffect(useCallback(() => { loadAll(); }, [loadAll]));

  const decide = async (p: NkProfile, like: boolean) => {
    setCards((old) => old.filter((x) => x.id !== p.id));
    Haptics.impactAsync(like ? Haptics.ImpactFeedbackStyle.Medium : Haptics.ImpactFeedbackStyle.Light);
    try {
      const r = like ? await api(`/nikah/p/${p.id}/interest/`, { body: { from_deck: 1 } }) : await api(`/nikah/p/${p.id}/skip/`, { body: {} });
      setLeft(r.left ?? null);
      if (r.match_id) {
        Alert.alert(t('Взаимная симпатия!'), t('Посмотрите, что дальше.'), [
          { text: t('Позже') }, { text: t('Открыть'), onPress: () => router.push(`/nikah/match/${r.match_id}`) }]);
      }
    } catch (e) {
      const err = e as ApiError;
      if (err.code === 'limit') setLeft(0);
      else Alert.alert(err.message);
      loadAll();
    }
  };

  const restore = async () => {
    try {
      const r = await api('/nikah/restore/', { body: {} });
      Alert.alert(r.restored ? t('Вернули в ленту: {n}.', { n: r.restored }) : t('Отклонённых анкет нет.'));
      loadAll();
    } catch (e: any) {
      Alert.alert(e.message, undefined, e.code === 'money' ? [{ text: t('Пополнить'), onPress: () => openWeb('/wallet/topup/') }, { text: 'OK' }] : undefined);
    }
  };

  if (!user) {
    return (
      <Screen title={t('Никях')} back>
        <Intro />
        <Button title={t('Войти, чтобы начать')} onPress={() => router.push('/login')} />
      </Screen>
    );
  }
  if (loading && !st) return <Screen title={t('Никях')} back><Loading /></Screen>;
  if (error && !st) return <Screen title={t('Никях')} back><Empty icon="cloud-offline-outline" title={error} action={<Button small kind="soft" title={t('Повторить')} onPress={loadAll} />} /></Screen>;
  if (!st?.profile) {
    return (
      <Screen title={t('Никях')} back>
        <Intro />
        <Button title={t('Заполнить анкету')} icon="create" onPress={() => router.push('/nikah/form')} />
        <Txt kind="small" style={{ textAlign: 'center' }}>{t('Около 5 минут. Анкету проверяет модератор.')}</Txt>
      </Screen>
    );
  }

  const nk = config?.features.nikah;
  const top = cards[0];
  return (
    <Screen title={t('Никях')} back scroll={false} right={
      <View style={{ flexDirection: 'row', gap: 16, alignItems: 'center' }}>
        <Pressable onPress={() => router.push('/nikah/filters')} hitSlop={8}>
          <Icon name={filtered ? 'funnel' : 'funnel-outline'} color={c.accent} />
        </Pressable>
        <Pressable onPress={() => router.push('/nikah/lists')} hitSlop={8}>
          <Icon name="heart-outline" color={c.accent} />
          <View style={{ position: 'absolute', right: -8, top: -6 }}><Badge n={(st.badges?.incoming ?? 0) + (st.badges?.waiting ?? 0)} /></View>
        </Pressable>
        <Pressable onPress={() => router.push('/nikah/me')} hitSlop={8}><Icon name="person-outline" color={c.accent} /></Pressable>
      </View>}>
      {!st.published ? (
        <Card soft style={{ flexDirection: 'row', gap: 10, alignItems: 'center', marginBottom: 10 }}>
          <Icon name="time-outline" color={c.warn} />
          <Txt kind="small" style={{ flex: 1, color: c.ink }}>
            {st.profile.status === 'rejected' ? t('Анкета отклонена модератором — исправьте её в разделе «Моя анкета».')
              : !st.profile.active ? t('Анкета на паузе — её никто не видит.')
              : t('Анкета на проверке. Лента откроется после одобрения — обычно до суток.')}
          </Txt>
        </Card>
      ) : null}
      {left !== null ? <Txt kind="small" style={{ textAlign: 'center', marginBottom: 6 }}>{t('Осталось анкет сегодня: {n}', { n: left })}</Txt> : null}
      <View style={{ flex: 1 }}>
        {loading ? <Loading /> : top ? (
          <>
            {cards[1] ? <DeckCard key={cards[1].id} p={cards[1]} behind /> : null}
            <DeckCard key={top.id} p={top} onDecide={(like) => decide(top, like)} />
          </>
        ) : left === 0 ? (
          <Empty icon="hourglass-outline" title={t('Анкеты на сегодня закончились')}
            text={nk?.premium ? t('С премиумом — без ограничений. Или загляните завтра, ин шаа Аллах.') : t('Загляните завтра, ин шаа Аллах.')}
            action={<View style={{ gap: 8, alignSelf: 'stretch' }}>
              {nk?.premium ? <Button title={t('Премиум: {p} сум / {d} дн.', { p: nk.premium_price.toLocaleString('ru-RU'), d: nk.premium_days })} onPress={() => router.push('/nikah/me')} /> : null}
            </View>} />
        ) : (
          <Empty icon="search-outline" title={filtered ? t('По фильтрам никого не нашлось') : t('Новых анкет пока нет')}
            action={<View style={{ gap: 8, alignSelf: 'stretch' }}>
              {filtered ? <Button kind="soft" title={t('Изменить фильтры')} onPress={() => router.push('/nikah/filters')} /> : null}
              {st.skipped ? <Button kind="ghost" title={t('Вернуть отклонённых ({n})', { n: st.skipped })} onPress={restore} /> : null}
            </View>} />
        )}
      </View>
      {top ? (
        <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 22, paddingVertical: 12 }}>
          <RoundBtn icon="close" color={c.bad} onPress={() => decide(top, false)} />
          <RoundBtn icon="document-text-outline" color={c.accent} small onPress={() => router.push(`/nikah/${top.id}`)} />
          <RoundBtn icon="heart" color={c.ok} onPress={() => (st.published ? decide(top, true) : Alert.alert(t('Интерес можно проявлять, когда вашу анкету одобрит модератор.')))} />
        </View>
      ) : null}
    </Screen>
  );
}

function RoundBtn({ icon, color, onPress, small }: { icon: any; color: string; onPress: () => void; small?: boolean }) {
  const { c } = useApp();
  const size = small ? 52 : 66;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => ({
      width: size, height: size, borderRadius: size / 2, backgroundColor: c.card, alignItems: 'center', justifyContent: 'center',
      borderWidth: 2, borderColor: color, transform: [{ scale: pressed ? 0.92 : 1 }],
      shadowColor: color, shadowOpacity: 0.35, shadowRadius: 12, elevation: 4 })}>
      <Icon name={icon} size={small ? 24 : 32} color={color} />
    </Pressable>
  );
}

/** Карточка колоды: тянешь вправо — интерес (зелёная галочка), влево — пропуск (красный крестик). */
function DeckCard({ p, onDecide, behind }: { p: NkProfile; onDecide?: (like: boolean) => void; behind?: boolean }) {
  const { c, t } = useApp();
  const { width } = useWindowDimensions();
  const x = useSharedValue(0);
  const y = useSharedValue(0);
  const limit = width * 0.28;

  const pan = Gesture.Pan()
    .enabled(!behind)
    .onUpdate((e) => {
      x.value = e.translationX;
      y.value = e.translationY * 0.3;
    })
    .onEnd((e) => {
      if (Math.abs(x.value) > limit || Math.abs(e.velocityX) > 900) {
        const like = x.value > 0;
        x.value = withTiming(like ? width * 1.5 : -width * 1.5, { duration: 220 });
        if (onDecide) scheduleOnRN(onDecide, like);
      } else {
        x.value = withSpring(0);
        y.value = withSpring(0);
      }
    });

  const style = useAnimatedStyle(() => ({
    transform: [{ translateX: x.value }, { translateY: y.value }, { rotate: `${interpolate(x.value, [-width, width], [-14, 14])}deg` }],
  }));
  const likeStyle = useAnimatedStyle(() => ({ opacity: interpolate(x.value, [0, limit], [0, 1], 'clamp') }));
  const nopeStyle = useAnimatedStyle(() => ({ opacity: interpolate(x.value, [-limit, 0], [1, 0], 'clamp') }));

  return (
    <GestureDetector gesture={pan}>
      <Animated.View style={[{
        position: 'absolute', left: 0, right: 0, top: behind ? 10 : 0, bottom: behind ? -6 : 4,
        transform: behind ? [{ scale: 0.95 }] : undefined, opacity: behind ? 0.6 : 1,
      }, !behind && style]}>
        <Pressable onPress={() => !behind && router.push(`/nikah/${p.id}`)} style={{
          flex: 1, backgroundColor: c.card, borderRadius: 28, padding: 18, gap: 14,
          shadowColor: '#15172a', shadowOpacity: 0.12, shadowRadius: 18, shadowOffset: { width: 0, height: 8 }, elevation: 4,
          borderWidth: 1, borderColor: c.line }}>
          <ProfileHead p={p} />
          {p.why?.length ? (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
              {p.why.slice(0, 4).map((w) => (
                <View key={w} style={{ backgroundColor: c.accentSoft, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 }}>
                  <Txt kind="small" color={c.accentD} style={{ fontSize: 12 }}>✓ {w}</Txt>
                </View>
              ))}
            </View>
          ) : null}
          <KV items={[[t('Вероубеждение'), p.aqida], [t('Мазхаб'), p.madhhab], [t('Намаз'), p.prayer],
            [p.gender === 'M' ? t('Борода') : t('Покрытие'), p.look], [t('Семейное положение'), p.marital], [t('Готовность'), p.ready_when]]} />
          <Txt kind="muted" numberOfLines={6}>{p.about}</Txt>
          <Txt kind="small" color={c.accent} style={{ marginTop: 'auto', textAlign: 'center' }}>{t('Нажмите, чтобы открыть анкету целиком')}</Txt>
          <Animated.View style={[{ position: 'absolute', top: 24, left: 24, transform: [{ rotate: '-14deg' }] }, likeStyle]}>
            <View style={{ width: 84, height: 84, borderRadius: 42, borderWidth: 4, borderColor: c.ok, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(18,161,80,0.12)',
              shadowColor: c.ok, shadowOpacity: 0.8, shadowRadius: 16, elevation: 8 }}>
              <Icon name="checkmark" size={50} color={c.ok} />
            </View>
          </Animated.View>
          <Animated.View style={[{ position: 'absolute', top: 24, right: 24, transform: [{ rotate: '14deg' }] }, nopeStyle]}>
            <View style={{ width: 84, height: 84, borderRadius: 42, borderWidth: 4, borderColor: c.bad, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(229,72,77,0.12)',
              shadowColor: c.bad, shadowOpacity: 0.8, shadowRadius: 16, elevation: 8 }}>
              <Icon name="close" size={50} color={c.bad} />
            </View>
          </Animated.View>
        </Pressable>
      </Animated.View>
    </GestureDetector>
  );
}

function Intro() {
  const { c, t, config } = useApp();
  const minutes = config?.features.nikah.photo_minutes ?? 10;
  const points: [any, string, string][] = [
    ['eye-off-outline', t('Анкеты без фото'), t('Сначала — убеждения, характер и цели. Фото открываются только при взаимной симпатии.')],
    ['shield-checkmark-outline', t('Фото под защитой'), t('Сестра смотрит первой, показ одноразовый — {m} минут, с водяным знаком. Скриншоты в приложении запрещены.', { m: minutes })],
    ['people-outline', t('Махрам рядом'), t('В переписку можно пригласить свидетеля — отца, брата или другого махрама.')],
    ['checkmark-done-outline', t('Модерация'), t('Каждую анкету проверяет человек. Контакты и ссылки в анкете и чате не пропускаются.')],
  ];
  return (
    <View style={{ gap: 12 }}>
      <Card style={{ alignItems: 'center', gap: 8, paddingVertical: 24 }}>
        <View style={{ width: 70, height: 70, borderRadius: 24, backgroundColor: '#fde8f0', alignItems: 'center', justifyContent: 'center' }}>
          <Icon name="heart" size={36} color="#e0457b" />
        </View>
        <Txt kind="h2" style={{ textAlign: 'center' }}>{t('Никях — знакомство для брака')}</Txt>
        <Txt kind="muted" style={{ textAlign: 'center' }}>{t('По Корану и Сунне, серьёзно и бережно.')}</Txt>
      </Card>
      {points.map(([icon, title, text]) => (
        <Card key={title} style={{ flexDirection: 'row', gap: 12 }}>
          <Icon name={icon} color={c.accent} />
          <View style={{ flex: 1, gap: 2 }}><Txt kind="h3">{title}</Txt><Txt kind="small">{text}</Txt></View>
        </Card>
      ))}
    </View>
  );
}
