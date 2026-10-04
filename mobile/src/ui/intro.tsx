/**
 * Вступление при первом запуске — как в Telegram: несколько экранов «что это и для чего», листаются пальцем.
 * На последнем человек выбирает, с чего начать: вся платформа или только общение — от этого зависят нижние кнопки
 * (потом меняются в Настройках → «Нижние кнопки»).
 */
import { useRef, useState } from 'react';
import { Pressable, ScrollView, useWindowDimensions, View, type NativeScrollEvent, type NativeSyntheticEvent } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useApp, type TabKey } from '@/state/app';

import { Button, Icon, Txt, type IconName } from './kit';

const PAGES: { icon: IconName; tint: string; title: string; text: string }[] = [
  { icon: 'sparkles', tint: '#6d5efc', title: 'ilm4 — всё нужное в одном приложении',
    text: 'Общение, вера и повседневные дела мусульманина. Без рекламы и лишнего шума.' },
  { icon: 'chatbubbles', tint: '#3b82f6', title: 'Общайтесь',
    text: 'Чаты и звонки, группы и каналы, лента записей и сообщества по интересам — с ролями и голосовыми комнатами.' },
  { icon: 'moon', tint: '#0ea5a5', title: 'Не пропускайте намаз',
    text: 'Точное время по вашему городу и азан, кибла, хадис дня и трекер привычек — одному или вместе с близкими.' },
  { icon: 'bag-handle', tint: '#f59e0b', title: 'Решайте дела',
    text: 'Объявления, работа и услуги, попутчики, халяль-места на карте, врачи и никях.' },
];

const MODES: { key: string; icon: IconName; title: string; text: string; tabs: TabKey[] }[] = [
  { key: 'all', icon: 'apps', title: 'Вся платформа', text: 'Главная, намаз, сервисы и чаты', tabs: ['home', 'prayer', 'services', 'chats'] },
  { key: 'talk', icon: 'chatbubbles', title: 'Только общение', text: 'Чаты, лента и сообщества', tabs: ['chats', 'feed', 'communities', 'services'] },
  { key: 'faith', icon: 'moon', title: 'Намаз и привычки', text: 'Намаз, трекер, главная', tabs: ['prayer', 'tracker', 'home', 'services'] },
];

export function Intro() {
  const { c, t, finishIntro, setTabs } = useApp();
  const { width } = useWindowDimensions();
  const ref = useRef<ScrollView>(null);
  const [page, setPage] = useState(0);
  const [mode, setMode] = useState('all');
  const last = PAGES.length;                      // последний экран — выбор «с чего начать»
  const go = (i: number) => ref.current?.scrollTo({ x: i * width, animated: true });
  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => setPage(Math.round(e.nativeEvent.contentOffset.x / width));
  const done = () => {
    setTabs(MODES.find((m) => m.key === mode)?.tabs ?? MODES[0].tabs);
    finishIntro();
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }}>
      <View style={{ flexDirection: 'row', justifyContent: 'flex-end', paddingHorizontal: 16, paddingTop: 6, minHeight: 40 }}>
        {page < last ? <Pressable onPress={() => go(last)} hitSlop={10} style={{ padding: 8 }}><Txt color={c.inkSoft} style={{ fontWeight: '600' }}>{t('Пропустить')}</Txt></Pressable> : null}
      </View>
      <ScrollView ref={ref} horizontal pagingEnabled showsHorizontalScrollIndicator={false} onScroll={onScroll} scrollEventThrottle={32} style={{ flex: 1 }} contentContainerStyle={{ flexGrow: 1 }}>
        {PAGES.map((p) => (
          <View key={p.title} style={{ width, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32, gap: 18 }}>
            <View style={{ width: 132, height: 132, borderRadius: 44, backgroundColor: `${p.tint}1f`, alignItems: 'center', justifyContent: 'center' }}>
              <Icon name={p.icon} size={64} color={p.tint} />
            </View>
            <Txt kind="h1" style={{ textAlign: 'center', fontSize: 26, lineHeight: 32 }}>{t(p.title)}</Txt>
            <Txt kind="muted" style={{ textAlign: 'center', fontSize: 16.5, lineHeight: 24 }}>{t(p.text)}</Txt>
          </View>
        ))}
        <View style={{ width, justifyContent: 'center', paddingHorizontal: 22, gap: 12 }}>
          <Txt kind="h1" style={{ textAlign: 'center', fontSize: 26, lineHeight: 32 }}>{t('С чего начнём?')}</Txt>
          <Txt kind="muted" style={{ textAlign: 'center', marginBottom: 6 }}>{t('От этого зависят кнопки внизу экрана. Поменять можно в любой момент в настройках.')}</Txt>
          {MODES.map((m) => {
            const on = mode === m.key;
            return (
              <Pressable key={m.key} onPress={() => setMode(m.key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, borderRadius: 20,
                backgroundColor: c.card, borderWidth: 2, borderColor: on ? c.accent : 'transparent' }}>
                <View style={{ width: 46, height: 46, borderRadius: 15, backgroundColor: on ? c.accent : c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name={m.icon} size={23} color={on ? '#fff' : c.accentD} />
                </View>
                <View style={{ flex: 1 }}>
                  <Txt style={{ fontWeight: '700', fontSize: 16.5 }}>{t(m.title)}</Txt>
                  <Txt kind="small">{t(m.text)}</Txt>
                </View>
                <Icon name={on ? 'radio-button-on' : 'radio-button-off'} size={22} color={on ? c.accent : c.line} />
              </Pressable>
            );
          })}
        </View>
      </ScrollView>
      <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 7, paddingVertical: 14 }}>
        {[...PAGES, null].map((_x, i) => <View key={i} style={{ width: page === i ? 22 : 7, height: 7, borderRadius: 4, backgroundColor: page === i ? c.accent : c.line }} />)}
      </View>
      <View style={{ paddingHorizontal: 22, paddingBottom: 14 }}>
        <Button title={page < last ? t('Далее') : t('Начать')} onPress={() => (page < last ? go(page + 1) : done())} />
      </View>
    </SafeAreaView>
  );
}
