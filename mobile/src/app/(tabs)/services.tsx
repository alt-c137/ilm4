import { Image } from 'expo-image';
import { useState } from 'react';
import { Pressable, View } from 'react-native';

import { MODULE_ICON, openModule } from '@/lib/modules';
import { useApp } from '@/state/app';
import { Card, Field, Icon, Screen, Section, Txt } from '@/ui/kit';

export default function Services() {
  const { c, t, config, refreshConfig } = useApp();
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const all = (config?.modules ?? []).filter((m) => !q || `${m.name} ${m.descr}`.toLowerCase().includes(q.toLowerCase()));
  const groups = [...(config?.groups ?? []), { key: 'more', name: t('Ещё') }];
  return (
    <Screen title={t('Сервисы')} onRefresh={async () => { setBusy(true); await refreshConfig(); setBusy(false); }} refreshing={busy}>
      <Field placeholder={t('Поиск по сервисам')} value={q} onChangeText={setQ} />
      {groups.map((g) => {
        const items = all.filter((m) => m.group === g.key);
        if (!items.length) return null;
        return (
          <Section key={g.key} title={g.name}>
            <Card style={{ paddingVertical: 4 }}>
              {items.map((m, i) => (
                <Pressable key={m.key} onPress={() => openModule(m.key, m.status, m.name)}
                  style={({ pressed }) => ({ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12,
                    borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line, opacity: pressed ? 0.6 : 1 })}>
                  <View style={{ width: 42, height: 42, borderRadius: 14, backgroundColor: m.status === 'on' ? c.accentSoft : c.card2, alignItems: 'center', justifyContent: 'center' }}>
                    {m.icon && m.icon.endsWith('.png') ? <Image source={{ uri: m.icon }} style={{ width: 24, height: 24 }} />
                      : <Icon name={MODULE_ICON[m.key] ?? 'apps'} size={22} color={m.status === 'on' ? c.accent : c.inkSoft} />}
                  </View>
                  <View style={{ flex: 1 }}>
                    <Txt kind="h3" style={{ fontWeight: '600' }} color={m.status === 'on' ? c.ink : c.inkSoft}>{m.name}</Txt>
                    {m.descr ? <Txt kind="small" numberOfLines={1}>{m.descr}</Txt> : null}
                  </View>
                  {m.status === 'soon' ? (
                    <View style={{ backgroundColor: c.card2, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 3 }}>
                      <Txt kind="small" style={{ fontSize: 11, fontWeight: '700' }}>{t('Скоро')}</Txt>
                    </View>
                  ) : <Icon name="chevron-forward" size={18} color={c.inkSoft} />}
                </Pressable>
              ))}
            </Card>
          </Section>
        );
      })}
    </Screen>
  );
}
