import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Alert, FlatList, KeyboardAvoidingView, Platform, Pressable, ScrollView, Switch, TextInput, View } from 'react-native';
import Animated, { Easing, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Circle, Defs, RadialGradient, Stop } from 'react-native-svg';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Icon, OfflineBar, Sheet, Txt, type IconName } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type M = { role: 'user' | 'assistant' | 'action' | 'wait' | 'error'; text: string };
type Provider = { key: string; name: string; model: string; where: string; custom: boolean };
type Brief = { hello: string; name: string; unread: number; notifications: number;
  prayer: { name: string; time: string; in: string; tomorrow: boolean; city: string } | null;
  tracker: { done: number; total: number; left: { id: number; title: string }[] } | null;
  plans: { title: string; date: string; today: boolean; time: string }[]; chats: { id: number; name: string; unread: number }[] };
type St = { own_key: string; provider: string; provider_name: string; model: string; site: boolean; free: number; left: number; unlimited: boolean;
  read_chats: boolean; ready: boolean; providers: Provider[]; chats: { id: number; title: string }[]; brief?: Brief };

const IDEAS: { say: string; label: string }[] = [
  { say: 'Сделай сводку моего дня: намаз, планы, трекер, кто мне написал', label: 'Отчёт за день' },
  { say: 'Кто мне написал и что у меня не прочитано?', label: 'Кто мне написал?' },
  { say: 'Найди халяль-кафе в Ташкенте', label: 'Халяль-кафе рядом' },
  { say: 'Добавь привычку: читать Коран 5 страниц каждый день, напоминание в 06:00', label: 'Привычка: Коран' },
  { say: 'Поставь встречу на завтра в 15:00: забрать справку', label: 'Встреча на завтра' }];

/** Шар помощника: мягкие пятна медленно вращаются; пока ИИ думает — быстрее. Только поворот — телефон не грузит. */
function Orb({ busy, size = 58 }: { busy: boolean; size?: number }) {
  const turn = useSharedValue(0);
  useEffect(() => {
    turn.set(0);
    turn.set(withRepeat(withTiming(1, { duration: busy ? 2200 : 9000, easing: Easing.linear }), -1));
  }, [busy, turn]);
  const style = useAnimatedStyle(() => ({ transform: [{ rotate: `${turn.get() * 360}deg` }] }));
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, overflow: 'hidden', backgroundColor: '#6d5efc' }}>
      <Animated.View style={[{ width: size, height: size }, style]}>
        <Svg width={size} height={size} viewBox="0 0 100 100">
          <Defs>
            <RadialGradient id="a" cx="30%" cy="30%" r="55%"><Stop offset="0" stopColor="#5eead4" stopOpacity={0.85} /><Stop offset="1" stopColor="#5eead4" stopOpacity={0} /></RadialGradient>
            <RadialGradient id="b" cx="72%" cy="62%" r="55%"><Stop offset="0" stopColor="#f0abfc" stopOpacity={0.85} /><Stop offset="1" stopColor="#f0abfc" stopOpacity={0} /></RadialGradient>
            <RadialGradient id="d" cx="45%" cy="85%" r="50%"><Stop offset="0" stopColor="#93c5fd" stopOpacity={0.8} /><Stop offset="1" stopColor="#93c5fd" stopOpacity={0} /></RadialGradient>
          </Defs>
          <Circle cx="50" cy="50" r="50" fill="url(#a)" /><Circle cx="50" cy="50" r="50" fill="url(#b)" /><Circle cx="50" cy="50" r="50" fill="url(#d)" />
        </Svg>
      </Animated.View>
    </View>
  );
}

/** ИИ-помощник: сводка дня (без ИИ), разговор, свой ИИ (Claude, OpenAI, Z.AI…), разрешение читать сообщения. */
export default function Assistant() {
  const { c, t } = useApp();
  const { data: st, setData: setSt, reload } = useFetch<St>('/assistant/');
  const [msgs, setMsgs] = useState<M[]>([]);
  const [chat, setChat] = useState<number | null>(null);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);
  const [keyOpen, setKeyOpen] = useState(false);
  const [provOpen, setProvOpen] = useState(false);
  const [key, setKey] = useState('');
  const [prov, setProv] = useState('');
  const [model, setModel] = useState('');
  const list = useRef<FlatList<M>>(null);

  const send = async (value?: string) => {
    const body = (value ?? text).trim();
    if (!body || busy) return;
    setText('');
    setBusy(true);
    setMsgs((old) => [...old, { role: 'user', text: body }, { role: 'wait', text: '…' }]);
    try {
      const r = await api<St & { chat: number; messages: M[] }>('/assistant/send/', { body: { text: body, chat }, timeout: 180000 });
      setChat(r.chat);
      setMsgs(r.messages);
      if (st) setSt({ ...st, left: r.left, own_key: r.own_key });
    } catch (e) {
      setMsgs((old) => [...old.filter((m) => m.role !== 'wait'), { role: 'error', text: (e as ApiError).message }]);
    } finally {
      setBusy(false);
    }
  };
  const open = async (id: number) => {
    try {
      const r = await api<{ messages: M[] }>(`/assistant/?chat=${id}`);
      setChat(id);
      setMsgs(r.messages);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const patch = async (body: Record<string, unknown>) => {
    try {
      const r = await api<St>('/assistant/key/', { body });
      if (st) setSt({ ...st, ...r, chats: st.chats, brief: st.brief });
      return true;
    } catch (e) {
      Alert.alert((e as ApiError).message);
      return false;
    }
  };
  const openKey = () => {
    const first = st?.provider || st?.providers[0]?.key || 'anthropic';
    setProv(first);
    setModel(st?.own_key ? st.model : st?.providers.find((p) => p.key === first)?.model ?? '');
    setKey('');
    setKeyOpen(true);
  };
  const saveKey = async () => { if (await patch({ key, provider: prov, model })) { setKeyOpen(false); reload(true); } };
  const cur = st?.providers.find((p) => p.key === prov);
  const b = st?.brief;

  const bubble = (m: M) => {
    const user = m.role === 'user';
    if (m.role === 'action') {
      return (
        <View style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: c.accentSoft, borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4 }}>
          <Icon name="checkmark-done" size={13} color={c.accentD} /><Txt kind="small" color={c.accentD} style={{ fontWeight: '700' }}>{m.text}</Txt>
        </View>
      );
    }
    if (m.role === 'error') return <Txt kind="small" color={c.bad} style={{ textAlign: 'center' }}>{m.text}</Txt>;
    return (
      <View style={{ alignSelf: user ? 'flex-end' : 'flex-start', maxWidth: '86%', paddingHorizontal: 14, paddingVertical: 10, borderRadius: 18,
        backgroundColor: user ? c.accent : c.card, borderBottomRightRadius: user ? 6 : 18, borderBottomLeftRadius: user ? 18 : 6, opacity: m.role === 'wait' ? 0.5 : 1 }}>
        <Txt selectable color={user ? '#fff' : c.ink} style={{ fontSize: 15.5, lineHeight: 22 }}>{m.text}</Txt>
      </View>
    );
  };
  const card = (icon: IconName, label: string, title: string, sub: string, onPress: () => void) => (
    <Pressable onPress={onPress} style={{ flexBasis: '100%', flexDirection: 'row', gap: 10, padding: 12, borderRadius: 16, backgroundColor: c.card2 }}>
      <Icon name={icon} size={21} color={c.accent} />
      <View style={{ flex: 1 }}>
        <Txt kind="small" style={{ fontSize: 11, fontWeight: '700', letterSpacing: 0.3, textTransform: 'uppercase' }}>{label}</Txt>
        <Txt style={{ fontWeight: '700', fontSize: 15 }} numberOfLines={1}>{title}</Txt>
        <Txt kind="small" style={{ fontSize: 12.5 }} numberOfLines={2}>{sub}</Txt>
      </View>
    </Pressable>
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }} edges={['top', 'bottom']}>
      <OfflineBar />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10 }}>
        <Pressable onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} hitSlop={10}><Icon name="chevron-back" size={27} color={c.accent} /></Pressable>
        <Txt kind="h3" style={{ flex: 1 }}>{t('ИИ-помощник')}</Txt>
        <Pressable onPress={() => setMenu(true)} hitSlop={10} style={{ padding: 4 }}><Icon name="ellipsis-vertical" size={21} /></Pressable>
      </View>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        {msgs.length ? (
          <FlatList ref={list} data={msgs} keyExtractor={(_m, i) => String(i)} contentContainerStyle={{ padding: 12, gap: 8 }}
            onContentSizeChange={() => list.current?.scrollToEnd({ animated: true })} renderItem={({ item }) => bubble(item)} />
        ) : (
          <ScrollView contentContainerStyle={{ padding: 12, gap: 12 }}>
            <View style={{ backgroundColor: c.card, borderRadius: 22, padding: 14, gap: 12 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
                <Orb busy={busy} />
                <View style={{ flex: 1 }}>
                  <Txt kind="h3">{b ? `${b.hello}, ${b.name}` : t('Ассаляму алейкум!')}</Txt>
                  <Txt kind="small">{t('Вот что важно сейчас')}</Txt>
                </View>
              </View>
              {b ? (
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                  {b.prayer ? card('moon-outline', b.prayer.tomorrow ? `${t('Ближайший намаз')} · ${t('завтра')}` : t('Ближайший намаз'),
                    `${b.prayer.name} · ${b.prayer.time}`, `${t('через')} ${b.prayer.in} · ${b.prayer.city}`, () => router.push('/prayer')) : null}
                  {b.tracker ? card('checkmark-circle-outline', t('Трекер сегодня'), t('{a} из {b}', { a: b.tracker.done, b: b.tracker.total }),
                    b.tracker.left.length ? `${t('Осталось:')} ${b.tracker.left.slice(0, 3).map((x) => x.title).join(', ')}` : b.tracker.total ? t('Всё выполнено') : t('Привычек пока нет'),
                    () => router.push('/tracker')) : null}
                  {card('chatbubble-outline', t('Сообщения'), b.unread ? `${t('Новых:')} ${b.unread}` : t('Новых нет'),
                    b.chats.length ? b.chats.slice(0, 3).map((x) => `${x.name} (${x.unread})`).join(', ') : t('Никто не писал'), () => router.push('/chats'))}
                  {b.tracker ? card('calendar-outline', t('Встречи и дела'), b.plans[0]?.title ?? t('Ничего не запланировано'),
                    b.plans[0] ? [b.plans[0].today ? t('сегодня') : b.plans[0].date.slice(8, 10) + '.' + b.plans[0].date.slice(5, 7), b.plans[0].time,
                      b.plans.length > 1 ? `${t('ещё')} ${b.plans.length - 1}` : ''].filter(Boolean).join(' · ') : t('Скажите помощнику — он поставит'),
                    () => router.push('/tracker')) : null}
                </View>
              ) : null}
              {st?.ready ? (
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                  {IDEAS.map((x) => (
                    <Pressable key={x.label} onPress={() => send(t(x.say))} style={{ backgroundColor: c.accentSoft, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 8 }}>
                      <Txt color={c.accentD} style={{ fontWeight: '700', fontSize: 13.5 }}>{t(x.label)}</Txt>
                    </Pressable>
                  ))}
                </View>
              ) : null}
            </View>
            {st && !st.ready ? (
              <View style={{ gap: 10 }}>
                <Txt kind="muted">{st.site ? t('На сегодня бесплатные сообщения закончились. Завтра будут новые — или подключите свой ИИ.')
                  : t('Сводка дня работает и так. Чтобы помощник отвечал и делал дела за вас, подключите свой ИИ — подойдёт Claude, OpenAI, Z.AI.')}</Txt>
                <Button title={t('Подключить свой ИИ')} icon="key" onPress={openKey} />
              </View>
            ) : null}
            {st ? (
              <View style={{ backgroundColor: c.card, borderRadius: 18, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={{ flex: 1, gap: 2 }}>
                  <Txt style={{ fontWeight: '700' }}>{t('Помощник может читать мои новые сообщения')}</Txt>
                  <Txt kind="small" style={{ fontSize: 12.5 }}>{t('Нужно для отчёта «кто написал и о чём». Тексты непрочитанных сообщений уйдут поставщику ИИ. Чаты никяха не передаются никогда.')}</Txt>
                </View>
                <Switch value={st.read_chats} onValueChange={(v) => { setSt({ ...st, read_chats: v }); patch({ read_chats: v }); }} trackColor={{ true: c.accent }} />
              </View>
            ) : null}
          </ScrollView>
        )}
        {st?.ready ? (
          <View style={{ backgroundColor: c.card, borderTopWidth: 0.5, borderTopColor: c.line, padding: 8, gap: 4 }}>
            <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
              <TextInput value={text} onChangeText={setText} multiline maxLength={4000} placeholder={t('Спросите или попросите что-нибудь сделать…')} placeholderTextColor={c.inkSoft}
                style={{ flex: 1, minHeight: 44, maxHeight: 140, backgroundColor: c.card2, borderRadius: 22, borderWidth: 1, borderColor: c.line, paddingHorizontal: 16, paddingTop: 11, paddingBottom: 11, fontSize: 16, color: c.ink }} />
              <Pressable onPress={() => send()} disabled={!text.trim() || busy} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: text.trim() && !busy ? c.accent : c.line, alignItems: 'center', justifyContent: 'center' }}>
                <Icon name="send" size={19} color="#fff" />
              </Pressable>
            </View>
            <Txt kind="small" style={{ textAlign: 'center', fontSize: 12 }}>{st.own_key ? `${t('Работает на вашем ключе')} · ${st.provider_name} · ${st.model}`
              : st.unlimited ? t('Подписка: без лимита') : t('Осталось бесплатных сообщений сегодня: {n}', { n: st.left })}</Txt>
          </View>
        ) : null}
      </KeyboardAvoidingView>
      <Sheet open={menu} onClose={() => setMenu(false)} items={[
        { icon: 'add', title: t('Новый разговор'), onPress: () => { setChat(null); setMsgs([]); reload(true); } },
        { icon: 'key-outline', title: st?.own_key ? `${t('Свой ИИ')} · ${st.provider_name} ${st.own_key}` : t('Подключить свой ИИ'), onPress: () => setTimeout(openKey, 300) },
        ...(st?.chats ?? []).slice(0, 8).map((x) => ({ icon: 'chatbubble-outline' as const, title: x.title, onPress: () => open(x.id) })),
      ]} />
      <Sheet open={keyOpen} onClose={() => setKeyOpen(false)} title={t('Свой ИИ')} items={[]} header={
        <View style={{ paddingHorizontal: 20, gap: 10, paddingBottom: 10 }}>
          <Txt kind="small">{t('Со своим ключом лимита нет — за ответы вы платите поставщику напрямую. Ключ хранится зашифрованным. Подписки Claude Pro и ChatGPT Plus подключить нельзя: они не выдают ключ для чужих программ. Подойдут API Anthropic и OpenAI, Z.AI (в том числе подписка Coding Plan), OpenRouter.')}</Txt>
          <Pressable onPress={() => setProvOpen(true)} style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: c.card2, borderRadius: 14, padding: 12, gap: 8 }}>
            <View style={{ flex: 1 }}><Txt kind="small">{t('Поставщик')}</Txt><Txt style={{ fontWeight: '700' }}>{cur?.name ?? prov}</Txt></View>
            <Icon name="chevron-down" size={18} color={c.inkSoft} />
          </Pressable>
          <TextInput value={key} onChangeText={setKey} placeholder={cur?.where ? `${t('Ключ API')} — ${cur.where}` : t('Ключ API')} placeholderTextColor={c.inkSoft} secureTextEntry autoCapitalize="none" autoCorrect={false}
            style={{ backgroundColor: c.card2, borderRadius: 14, padding: 12, fontSize: 16, color: c.ink }} />
          <TextInput value={model} onChangeText={setModel} placeholder={t('Модель (можно не трогать)')} placeholderTextColor={c.inkSoft} autoCapitalize="none" autoCorrect={false}
            style={{ backgroundColor: c.card2, borderRadius: 14, padding: 12, fontSize: 16, color: c.ink }} />
          <Button title={t('Сохранить')} onPress={saveKey} disabled={!key.trim()} />
          {st?.own_key ? <Button kind="ghost" title={t('Удалить ключ')} onPress={async () => { if (await patch({ key: '' })) { setKeyOpen(false); reload(true); } }} /> : null}
        </View>} />
      <Sheet open={provOpen} onClose={() => setProvOpen(false)} title={t('Поставщик')}
        items={(st?.providers ?? []).filter((p) => !p.custom).map((p) => ({ title: p.name, subtitle: p.where, on: p.key === prov, onPress: () => { setProv(p.key); setModel(p.model); } }))} />
    </SafeAreaView>
  );
}
