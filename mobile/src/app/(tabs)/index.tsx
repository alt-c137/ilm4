import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { useEffect, useState, type ReactNode } from 'react';
import { Pressable, View } from 'react-native';

import { gregText, hijriText } from '@/lib/hijri';
import { MODULE_ICON, openModule } from '@/lib/modules';
import { PRAYER_NAMES } from '@/lib/notify';
import { useApp } from '@/state/app';
import { load, save } from '@/lib/storage';
import { Badge, Card, Icon, Screen, Section, Segmented, Txt, type IconName } from '@/ui/kit';
import { Showcase } from '@/ui/showcase';
import { useFetch } from '@/ui/useFetch';
import { fmtLeft, usePrayerNow } from '@/ui/usePrayer';

type Home = {
  hadith: { text: string; source: string; details: string; image: string } | null;
  rates: { code: string; rate: number }[];
  news: { id: number; title: string; summary: string; image: string; created_at: string }[];
  unread: number; chats_unread?: number; tracker?: { done: number; total: number };
};

/** Плитка «что вас ждёт»: раздел, которым пользуются каждый день, и что в нём нового. */
function NowTile({ icon, title, note, hot, onPress }: { icon: IconName; title: string; note: string; hot?: boolean; onPress: () => void }) {
  const { c } = useApp();
  return (
    <Pressable onPress={onPress} style={({ pressed }) => ({ flex: 1, minWidth: '46%', gap: 8, backgroundColor: c.card,
      borderRadius: 20, padding: 14, opacity: pressed ? 0.7 : 1 })}>
      <View style={{ width: 36, height: 36, borderRadius: 12, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
        <Icon name={icon} size={19} color={c.accentD} />
      </View>
      <View>
        <Txt style={{ fontWeight: '700', fontSize: 15.5 }} numberOfLines={1}>{title}</Txt>
        <Txt kind="small" numberOfLines={1} color={hot ? c.accent : undefined} style={hot ? { fontWeight: '700' } : undefined}>{note}</Txt>
      </View>
    </Pressable>
  );
}

/** Главная — всегда главная. Лента — отдельный раздел (нижняя кнопка или «Сервисы»), стартовый экран человек выбирает сам. */
export default function HomeScreen() {
  return <HomeMain switcher={null} />;
}

function HomeMain({ switcher }: { switcher: ReactNode }) {
  const { c, t, config, user, prayer, moduleOn } = useApp();
  const { data, reload, loading } = useFetch<Home>('/home/');
  const p = usePrayerNow();
  const [more, setMore] = useState(false);
  const [view, setView] = useState<'showcase' | 'brief'>('showcase');
  useEffect(() => { load<'showcase' | 'brief'>('home_view', 'showcase').then(setView); }, []);
  const today = new Date();
  const modules = (config?.modules ?? []).filter((m) => m.status === 'on' && m.key !== 'wallet');
  // разделы по смыслу; «Общение» — первым: с него начинают чаще всего
  const groups = [...(config?.groups ?? []), { key: 'more', name: t('Ещё') }].sort((a, b) => Number(a.key !== 'talk') - Number(b.key !== 'talk'));
  const tr = data?.tracker;

  return (
    <Screen onRefresh={() => reload()} refreshing={loading && !!data}>
      {switcher}
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

      <Segmented value={view} onChange={(v) => { setView(v); save('home_view', v); }}
        options={[{ key: 'showcase', label: t('Витрина') }, { key: 'brief', label: t('Сводка') }]} />
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

      {/* вид главной: «Витрина» — сервисы живыми плитками; «Сводка» — что ждёт + разделы по группам. Выбор запоминается. */}
      {view === 'showcase' ? <Showcase skip={['prayer']} /> : (
      <>
      {/* что вас ждёт — главное, ради чего открывают приложение каждый день */}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        {moduleOn('chat') ? <NowTile icon="chatbubbles" title={t('Чаты')} hot={!!data?.chats_unread}
          note={!user ? t('личные, группы, каналы') : data?.chats_unread ? t('новых: {n}', { n: data.chats_unread }) : t('нет новых')} onPress={() => router.push('/chats')} /> : null}
        {moduleOn('feed') ? <NowTile icon="albums" title={t('Лента')} note={t('записи людей')} onPress={() => router.push('/tab-feed')} /> : null}
        {moduleOn('communities') ? <NowTile icon="people" title={t('Сообщества')} note={t('клубы по интересам')} onPress={() => router.push('/space')} /> : null}
        {moduleOn('tracker') ? <NowTile icon="checkmark-circle" title={t('Трекер')} hot={!!tr && tr.total > 0 && tr.done < tr.total}
          note={tr && tr.total ? t('{done} из {total}', { done: tr.done, total: tr.total }) : t('привычки и дела')} onPress={() => router.push('/tracker')} /> : null}
      </View>

      {groups.map((g) => {
        const items = modules.filter((m) => m.group === g.key);
        if (!items.length) return null;
        return (
          <Section key={g.key} title={g.name} action={g.key === 'talk' ? <Pressable onPress={() => router.push('/services')}><Txt kind="small" color={c.accent}>{t('Все сервисы')}</Txt></Pressable> : undefined}>
            <Card style={{ flexDirection: 'row', flexWrap: 'wrap', paddingVertical: 14, paddingHorizontal: 6, rowGap: 14 }}>
              {items.map((m) => (
                <Pressable key={m.key} onPress={() => openModule(m.key, m.status, m.name)}
                  style={({ pressed }) => ({ width: '25%', alignItems: 'center', gap: 6, opacity: pressed ? 0.6 : 1 })}>
                  <View style={{ width: 52, height: 52, borderRadius: 17, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
                    {m.icon && m.icon.endsWith('.png') ? <Image source={{ uri: m.icon }} style={{ width: 27, height: 27 }} />
                      : <Icon name={MODULE_ICON[m.key] ?? 'apps'} size={24} color={c.accentD} />}
                  </View>
                  <Txt kind="small" numberOfLines={2} style={{ textAlign: 'center', color: c.ink, fontSize: 12, paddingHorizontal: 2 }}>{m.name}</Txt>
                </Pressable>
              ))}
            </Card>
          </Section>
        );
      })}

      </>
      )}

      {view === 'brief' && data?.news?.length ? (
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

      {view === 'brief' && data?.rates?.length ? (
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
