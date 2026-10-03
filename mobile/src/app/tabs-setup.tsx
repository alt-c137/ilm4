import { useState } from 'react';
import { Pressable, View } from 'react-native';

import { DEFAULT_TABS, TAB_SLOTS, useApp, type TabKey } from '@/state/app';
import { Button, Card, Icon, Screen, Section, Txt } from '@/ui/kit';

import { TAB_INFO } from './(tabs)/_layout';

/** Нижние кнопки: что держать под рукой и в каком порядке. «Профиль» всегда последний. */
export default function TabsSetup() {
  const { c, t, tabs, setTabs, moduleOn, config } = useApp();
  const [picked, setPicked] = useState<TabKey[]>(tabs);
  const all = (Object.keys(TAB_INFO) as TabKey[]).filter((k) => !TAB_INFO[k].module || !config || moduleOn(TAB_INFO[k].module!));
  const rest = all.filter((k) => !picked.includes(k));
  const apply = (next: TabKey[]) => { setPicked(next); if (next.length >= 2) setTabs(next); };
  const move = (i: number, by: number) => {
    const next = [...picked];
    const j = i + by;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    apply(next);
  };
  const round = { width: 34, height: 34, borderRadius: 17, alignItems: 'center' as const, justifyContent: 'center' as const, backgroundColor: c.card2 };

  return (
    <Screen title={t('Нижние кнопки')} back>
      <Txt kind="muted">{t('Выберите до пяти разделов, которые будут внизу экрана, и их порядок. Остальные всегда есть в «Сервисах».')}</Txt>
      <Section title={t('Внизу экрана')}>
        <Card style={{ paddingVertical: 4 }}>
          {picked.map((k, i) => (
            <View key={k} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
              <Icon name={TAB_INFO[k].icon} size={22} color={c.accent} />
              <Txt style={{ flex: 1, fontWeight: '700' }}>{t(TAB_INFO[k].title)}</Txt>
              <Pressable onPress={() => move(i, -1)} disabled={i === 0} style={[round, { opacity: i === 0 ? 0.35 : 1 }]} accessibilityLabel={t('Выше')}><Icon name="chevron-up" size={18} /></Pressable>
              <Pressable onPress={() => move(i, 1)} disabled={i === picked.length - 1} style={[round, { opacity: i === picked.length - 1 ? 0.35 : 1 }]} accessibilityLabel={t('Ниже')}><Icon name="chevron-down" size={18} /></Pressable>
              <Pressable onPress={() => apply(picked.filter((x) => x !== k))} disabled={picked.length <= 2} style={[round, { opacity: picked.length <= 2 ? 0.35 : 1 }]} accessibilityLabel={t('Убрать')}>
                <Icon name="remove" size={18} color={c.bad} />
              </Pressable>
            </View>
          ))}
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 11, borderTopWidth: 0.5, borderTopColor: c.line, opacity: 0.6 }}>
            <Icon name="person-circle" size={22} color={c.inkSoft} />
            <Txt style={{ flex: 1, fontWeight: '700' }}>{t('Профиль')}</Txt>
            <Txt kind="small">{t('всегда на месте')}</Txt>
          </View>
        </Card>
      </Section>
      {rest.length ? (
        <Section title={t('Можно добавить')}>
          <Card style={{ paddingVertical: 4 }}>
            {rest.map((k, i) => (
              <Pressable key={k} onPress={() => picked.length < TAB_SLOTS && apply([...picked, k])} disabled={picked.length >= TAB_SLOTS}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 11, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line, opacity: picked.length >= TAB_SLOTS ? 0.45 : 1 }}>
                <Icon name={`${TAB_INFO[k].icon}-outline` as any} size={22} color={c.inkSoft} />
                <Txt style={{ flex: 1, fontWeight: '600' }}>{t(TAB_INFO[k].title)}</Txt>
                <Icon name="add-circle" size={24} color={c.accent} />
              </Pressable>
            ))}
          </Card>
          {picked.length > 4 ? <Txt kind="small">{t('Кнопок больше пяти — нижняя панель листается пальцем. Первая кнопка — экран, с которого открывается приложение.')}</Txt> : null}
        </Section>
      ) : null}
      <Button kind="ghost" title={t('Как было')} onPress={() => apply(DEFAULT_TABS)} />
    </Screen>
  );
}
