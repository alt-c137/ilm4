import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, View } from 'react-native';

import { gregText, hijriText } from '@/lib/hijri';
import { MODULE_ICON, openModule } from '@/lib/modules';
import { PRAYER_NAMES } from '@/lib/notify';
import { useApp } from '@/state/app';
import { Badge, Card, Icon, Screen, Section, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';
import { fmtLeft, usePrayerNow } from '@/ui/usePrayer';

type Home = {
  hadith: { text: string; source: string; details: string; image: string } | null;
  rates: { code: string; rate: number }[];
  news: { id: number; title: string; summary: string; image: string; created_at: string }[];
  unread: number;
};

export default function HomeScreen() {
  const { c, t, config, user, prayer, moduleOn } = useApp();
  const { data, reload, loading } = useFetch<Home>('/home/');
  const p = usePrayerNow();
  const [more, setMore] = useState(false);
  const today = new Date();
  const modules = (config?.modules ?? []).filter((m) => m.status === 'on' && m.key !== 'chat');

  return (
    <Screen onRefresh={() => reload()} refreshing={loading && !!data}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <View style={{ flex: 1 }}>
          <Txt kind="h1">ilm<Txt kind="h1" color={c.accent}>4</Txt></Txt>
          <Txt kind="small">{gregText(today)} · {hijriText(today)}</Txt>
        </View>
        {user ? (
          <Pressable onPress={() => router.push('/notifications')} hitSlop={10} style={{ padding: 6 }}>
            <Icon name="notifications-outline" size={26} />
            <View style={{ position: 'absolute', right: 0, top: 0 }}><Badge n={data?.unread ?? 0} /></View>
          </Pressable>
        ) : (
          <Pressable onPress={() => router.push('/login')} style={{ backgroundColor: c.accent, borderRadius: 999, paddingVertical: 8, paddingHorizontal: 16 }}>
            <Txt kind="h3" color="#fff">{t('Войти')}</Txt>
          </Pressable>
        )}
      </View>

      {config?.notice ? (
        <Card soft style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
          <Icon name="information-circle" color={c.accent} />
          <Txt style={{ flex: 1 }}>{config.notice}</Txt>
        </Card>
      ) : null}

      {p && prayer.place ? (
        <Pressable onPress={() => router.push('/prayer')}>
          <LinearGradient colors={[c.accent, c.accentD]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={{ borderRadius: 26, padding: 20, gap: 12 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <Txt kind="label" color="rgba(255,255,255,0.8)">{t('Следующий намаз')} · {prayer.place.name}</Txt>
              <Icon name="location-outline" size={16} color="rgba(255,255,255,0.8)" />
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between' }}>
              <View>
                <Txt style={{ fontSize: 30, lineHeight: 36, fontWeight: '800' }} color="#fff">{t(PRAYER_NAMES[p.next.key])}</Txt>
                <Txt color="rgba(255,255,255,0.85)">{t('через {time}', { time: fmtLeft(p.left) })}</Txt>
              </View>
              <Txt style={{ fontSize: 40, lineHeight: 46, fontWeight: '800', fontVariant: ['tabular-nums'] }} color="#fff">
                {`${String(p.next.at.getHours()).padStart(2, '0')}:${String(p.next.at.getMinutes()).padStart(2, '0')}`}
              </Txt>
            </View>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', backgroundColor: 'rgba(255,255,255,0.14)', borderRadius: 16, padding: 10 }}>
              {(['fajr', 'dhuhr', 'asr', 'maghrib', 'isha'] as const).map((k) => (
                <View key={k} style={{ alignItems: 'center', flex: 1, opacity: p.current === k ? 1 : 0.8 }}>
                  <Txt kind="small" color="#fff" style={{ fontWeight: p.current === k ? '800' : '500' }}>{t(PRAYER_NAMES[k])}</Txt>
                  <Txt kind="h3" color="#fff">{p.today.times[k]}</Txt>
                </View>
              ))}
            </View>
          </LinearGradient>
        </Pressable>
      ) : null}

      {data?.hadith ? (
        <Card onPress={() => setMore((x) => !x)} style={{ gap: 8 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Icon name="book-outline" size={18} color={c.accent} />
            <Txt kind="label">{t('Хадис дня')}</Txt>
          </View>
          <Txt style={{ fontSize: 17, lineHeight: 24, fontWeight: '600' }}>{data.hadith.text}</Txt>
          <Txt kind="small">{data.hadith.source}</Txt>
          {more && data.hadith.details ? <Txt kind="muted">{data.hadith.details}</Txt> : null}
          {data.hadith.details && !more ? <Txt kind="small" color={c.accent}>{t('Подробнее')}</Txt> : null}
        </Card>
      ) : null}

      {moduleOn('nikah') ? (
        <Card onPress={() => router.push('/nikah')} style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
          <View style={{ width: 52, height: 52, borderRadius: 18, backgroundColor: '#fde8f0', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="heart" size={26} color="#e0457b" />
          </View>
          <View style={{ flex: 1 }}>
            <Txt kind="h3">{t('Никях')}</Txt>
            <Txt kind="small">{t('Знакомство для брака по Корану и Сунне')}</Txt>
          </View>
          <Icon name="chevron-forward" size={18} color={c.inkSoft} />
        </Card>
      ) : null}

      <Section title={t('Сервисы')} action={<Pressable onPress={() => router.push('/services')}><Txt kind="small" color={c.accent}>{t('Все')}</Txt></Pressable>}>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
          {modules.slice(0, 8).map((m) => (
            <Pressable key={m.key} onPress={() => openModule(m.key, m.status, m.name)}
              style={({ pressed }) => ({ width: '22.8%', alignItems: 'center', gap: 6, opacity: pressed ? 0.6 : 1 })}>
              <View style={{ width: 58, height: 58, borderRadius: 19, backgroundColor: c.card, alignItems: 'center', justifyContent: 'center' }}>
                {m.icon && m.icon.endsWith('.png') ? <Image source={{ uri: m.icon }} style={{ width: 30, height: 30 }} />
                  : <Icon name={MODULE_ICON[m.key] ?? 'apps'} size={26} color={c.accent} />}
              </View>
              <Txt kind="small" numberOfLines={2} style={{ textAlign: 'center', color: c.ink, fontSize: 12 }}>{m.name}</Txt>
            </Pressable>
          ))}
        </View>
      </Section>

      {data?.news?.length ? (
        <Section title={t('Новости')} action={<Pressable onPress={() => router.push('/news')}><Txt kind="small" color={c.accent}>{t('Все')}</Txt></Pressable>}>
          {data.news.slice(0, 3).map((n) => (
            <Card key={n.id} onPress={() => router.push(`/news/${n.id}`)} style={{ flexDirection: 'row', gap: 12, padding: 12 }}>
              {n.image ? <Image source={{ uri: n.image }} style={{ width: 72, height: 72, borderRadius: 14 }} contentFit="cover" /> : null}
              <View style={{ flex: 1, gap: 4 }}>
                <Txt kind="h3" numberOfLines={2}>{n.title}</Txt>
                {n.summary ? <Txt kind="small" numberOfLines={2}>{n.summary}</Txt> : null}
              </View>
            </Card>
          ))}
        </Section>
      ) : null}

      {data?.rates?.length ? (
        <Section title={t('Курсы к суму')}>
          <Card style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 16 }}>
            {data.rates.slice(0, 6).map((r) => (
              <View key={r.code} style={{ minWidth: '28%' }}>
                <Txt kind="small">{r.code}</Txt>
                <Txt kind="h3">{Math.round(r.rate).toLocaleString('ru-RU')}</Txt>
              </View>
            ))}
          </Card>
        </Section>
      ) : null}
    </Screen>
  );
}
