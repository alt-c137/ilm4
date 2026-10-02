/** Общие части никяха: карточка анкеты, совместимость, строки «ключ — значение». */
import { View } from 'react-native';

import { useApp } from '@/state/app';

import { Icon, Txt } from './kit';

export type NkProfile = {
  id: number; name: string; age: number; gender: 'M' | 'F'; place: string; nationality: string; height: number | null; weight: number | null;
  verified: boolean; online: boolean; premium: boolean; boosted: boolean; has_photo: boolean;
  marital: string; madhhab: string; aqida: string; prayer: string; look: string; ready_when: string; about: string;
  compat?: number; why?: string[]; saved?: boolean;
  quran?: string; where_allah?: string; wife_number?: string; polygyny?: string; children_want?: string; children_accept?: string;
  relocation?: string; manhaj_text?: string; partner_expectations?: string; age_from?: number; age_to?: number;
};

export function Compat({ value, size = 56 }: { value: number; size?: number }) {
  const { c, t } = useApp();
  const color = value >= 75 ? c.ok : value >= 50 ? c.accent : c.warn;
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, borderWidth: 4, borderColor: color, alignItems: 'center', justifyContent: 'center', backgroundColor: c.card }}>
      <Txt style={{ fontWeight: '800', fontSize: size * (value >= 100 ? 0.22 : 0.27) }} color={color}>{value}%</Txt>
      {size > 60 ? <Txt kind="small" style={{ fontSize: 9 }}>{t('совместимость')}</Txt> : null}
    </View>
  );
}

export function KV({ items }: { items: [string, string | number | null | undefined][] }) {
  const { c } = useApp();
  const rows = items.filter(([, v]) => v !== '' && v !== null && v !== undefined);
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
      {rows.map(([k, v]) => (
        <View key={k} style={{ backgroundColor: c.card2, borderRadius: 14, paddingHorizontal: 12, paddingVertical: 8, minWidth: '47%', flexGrow: 1 }}>
          <Txt kind="small" style={{ fontSize: 11 }}>{k}</Txt>
          <Txt style={{ fontWeight: '600', fontSize: 14 }}>{String(v)}</Txt>
        </View>
      ))}
    </View>
  );
}

export function ProfileHead({ p }: { p: NkProfile }) {
  const { c, t } = useApp();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
      <View style={{ width: 58, height: 58, borderRadius: 20, backgroundColor: p.gender === 'F' ? '#fde8f0' : c.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
        <Icon name={p.gender === 'F' ? 'flower' : 'person'} size={28} color={p.gender === 'F' ? '#e0457b' : c.accent} />
      </View>
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <Txt kind="h2" numberOfLines={1}>{p.name}, {p.age}</Txt>
          {p.verified ? <Icon name="checkmark-circle" size={18} color={c.ok} /> : null}
        </View>
        <Txt kind="small" numberOfLines={1}>{[p.place, p.nationality].filter(Boolean).join(' · ')}</Txt>
        <View style={{ flexDirection: 'row', gap: 10, marginTop: 2 }}>
          {p.online ? <Txt kind="small" color={c.ok}>● {t('в сети')}</Txt> : null}
          {p.has_photo ? <Txt kind="small">📷 {t('фото при симпатии')}</Txt> : null}
        </View>
      </View>
      {p.compat !== undefined ? <Compat value={p.compat} /> : null}
    </View>
  );
}
