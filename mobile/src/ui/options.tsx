/** Выбор варианта: крупные карточки (как в анкете бота). */
import { Pressable, View } from 'react-native';

import { useApp } from '@/state/app';

import { Icon, Txt } from './kit';

export type Opt = { key: string | number; name: string };

export function OptionList({ options, value, onChange, allowClear }: {
  options: Opt[]; value: string | number | null | undefined; onChange: (v: any) => void; allowClear?: boolean;
}) {
  const { c } = useApp();
  return (
    <View style={{ gap: 8 }}>
      {options.map((o) => {
        const on = String(value ?? '') === String(o.key);
        return (
          <Pressable key={String(o.key)} onPress={() => onChange(on && allowClear ? '' : o.key)} style={({ pressed }) => ({
            flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, borderRadius: 16, borderWidth: 1.5,
            borderColor: on ? c.accent : c.line, backgroundColor: on ? c.accentSoft : c.card, opacity: pressed ? 0.8 : 1 })}>
            <Txt style={{ flex: 1, fontWeight: on ? '700' : '500' }} color={on ? c.accentD : c.ink}>{o.name}</Txt>
            <Icon name={on ? 'checkmark-circle' : 'ellipse-outline'} size={22} color={on ? c.accent : c.line} />
          </Pressable>
        );
      })}
    </View>
  );
}
