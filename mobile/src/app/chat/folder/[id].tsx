import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, Switch, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Avatar, Button, Card, Field, Icon, Loading, Screen, Section, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

import type { Folder } from '../folders';

type Chat = { id: number; title: string; avatar: string; other_id: number | null; saved?: boolean };
type Meta = { items: Folder[]; types: { key: string; name: string }[] };

const TYPE_HINT: Record<string, string> = {
  personal: 'Переписка с людьми, поддержка, «Избранное»', ads: 'Чаты по объявлениям, вакансиям, услугам, поездкам',
  nikah: 'Знакомства для никяха', groups: 'Все группы, где вы состоите', channels: 'Все каналы, на которые вы подписаны',
};

/** Папка чатов: название, значок, какие типы чатов входят, какие чаты добавить или исключить поимённо. */
export default function FolderEdit() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const fresh = id === 'new';
  const { c, t } = useApp();
  const meta = useFetch<Meta>('/chat/folders/');
  const chats = useFetch<{ items: Chat[] }>('/chat/');
  const [draft, setDraft] = useState<Folder | null>(null);
  const [pickFor, setPickFor] = useState<'include' | 'exclude' | null>(null);
  const [busy, setBusy] = useState(false);

  const source = fresh ? null : meta.data?.items.find((f) => String(f.id) === id) ?? null;
  const base: Folder = { id: 0, title: '', emoji: '', types: [], no_muted: false, no_read: false, no_archived: true, include: [], exclude: [] };
  const f: Folder | null = draft ?? (fresh ? base : source);
  if (!f || !meta.data) return <Screen title={t('Папка')} back><Loading /></Screen>;

  const set = (part: Partial<Folder>) => setDraft({ ...f, ...part });
  const flip = (key: 'include' | 'exclude', cid: number) => {
    const has = f[key].includes(cid);
    const other = key === 'include' ? 'exclude' : 'include';
    setDraft({ ...f, [key]: has ? f[key].filter((x) => x !== cid) : [...f[key], cid], [other]: f[other].filter((x) => x !== cid) } as Folder);
  };
  const save = async () => {
    if (!f.title.trim()) return Alert.alert(t('Дайте папке название.'));
    setBusy(true);
    try {
      await api(fresh ? '/chat/folders/' : `/chat/folders/${id}/`, { body: { ...f, title: f.title.trim() } });
      router.back();
    } catch (e) {
      Alert.alert((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };
  const all = chats.data?.items ?? [];
  const names = (ids: number[]) => all.filter((x) => ids.includes(x.id)).map((x) => x.title);
  const check = (on: boolean) => (
    <View style={{ width: 24, height: 24, borderRadius: 7, borderWidth: 2, borderColor: on ? c.accent : c.line, backgroundColor: on ? c.accent : 'transparent', alignItems: 'center', justifyContent: 'center' }}>
      {on ? <Icon name="checkmark" size={16} color="#fff" /> : null}
    </View>
  );

  if (pickFor) {
    return (
      <Screen title={pickFor === 'include' ? t('Добавить чаты') : t('Исключить чаты')} back={false}
        right={<Pressable onPress={() => setPickFor(null)} hitSlop={10}><Txt color={c.accent} style={{ fontWeight: '800', fontSize: 16 }}>{t('Готово')}</Txt></Pressable>}>
        <Card style={{ paddingVertical: 4 }}>
          {all.length ? all.map((x, i) => (
            <Pressable key={x.id} onPress={() => flip(pickFor, x.id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 8, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
              {x.saved ? <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: '#5b76f7', alignItems: 'center', justifyContent: 'center' }}><Icon name="bookmark" size={18} color="#fff" /></View>
                : <Avatar uri={x.avatar} name={x.title} size={40} hue={x.other_id ?? x.id} />}
              <Txt style={{ flex: 1, fontWeight: '600' }} numberOfLines={1}>{x.title}</Txt>
              {check(f[pickFor].includes(x.id))}
            </Pressable>
          )) : <Txt kind="muted" style={{ padding: 12 }}>{t('Чатов пока нет.')}</Txt>}
        </Card>
      </Screen>
    );
  }

  return (
    <Screen title={fresh ? t('Новая папка') : t('Папка')} back
      right={<Pressable onPress={save} disabled={busy} hitSlop={10}><Txt color={c.accent} style={{ fontWeight: '800', fontSize: 16 }}>{t('Готово')}</Txt></Pressable>}>
      <Section title={t('Название')}>
        <Field value={f.title} onChangeText={(v) => set({ title: v })} maxLength={24} placeholder={t('Название папки')} />
      </Section>

      <Section title={t('Что входит в папку')}>
        <Card style={{ paddingVertical: 4 }}>
          {meta.data.types.map((ty, i) => {
            const on = f.types.includes(ty.key);
            return (
              <Pressable key={ty.key} onPress={() => set({ types: on ? f.types.filter((x) => x !== ty.key) : [...f.types, ty.key] })}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
                {check(on)}
                <View style={{ flex: 1 }}>
                  <Txt style={{ fontWeight: '700' }}>{ty.name}</Txt>
                  {TYPE_HINT[ty.key] ? <Txt kind="small">{t(TYPE_HINT[ty.key])}</Txt> : null}
                </View>
              </Pressable>
            );
          })}
        </Card>
        <Card onPress={() => setPickFor('include')} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <Icon name="add-circle" size={24} color={c.accent} />
          <View style={{ flex: 1 }}>
            <Txt style={{ fontWeight: '700' }} color={c.accent}>{t('Добавить чаты поимённо')}</Txt>
            {f.include.length ? <Txt kind="small" numberOfLines={2}>{names(f.include).join(', ')}</Txt> : null}
          </View>
          {f.include.length ? <Txt style={{ fontWeight: '800' }} color={c.accentD}>{f.include.length}</Txt> : null}
        </Card>
      </Section>

      <Section title={t('Что не показывать')}>
        <Card style={{ paddingVertical: 4 }}>
          {([['no_muted', 'Без звука', 'Чаты, у которых выключен звук'], ['no_read', 'Прочитанные', 'Останутся только чаты с новыми сообщениями'],
            ['no_archived', 'Из архива', 'Чаты, убранные в архив']] as const).map(([key, title, hint], i) => (
            <View key={key} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 9, borderTopWidth: i ? 0.5 : 0, borderTopColor: c.line }}>
              <View style={{ flex: 1 }}>
                <Txt style={{ fontWeight: '700' }}>{t(title)}</Txt>
                <Txt kind="small">{t(hint)}</Txt>
              </View>
              <Switch value={f[key]} onValueChange={(v) => set({ [key]: v } as Partial<Folder>)} trackColor={{ true: c.accent, false: c.line }} />
            </View>
          ))}
        </Card>
        <Card onPress={() => setPickFor('exclude')} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <Icon name="remove-circle" size={24} color={c.bad} />
          <View style={{ flex: 1 }}>
            <Txt style={{ fontWeight: '700' }} color={c.bad}>{t('Исключить чаты поимённо')}</Txt>
            {f.exclude.length ? <Txt kind="small" numberOfLines={2}>{names(f.exclude).join(', ')}</Txt> : null}
          </View>
          {f.exclude.length ? <Txt style={{ fontWeight: '800' }}>{f.exclude.length}</Txt> : null}
        </Card>
      </Section>
      <Button title={fresh ? t('Создать папку') : t('Сохранить')} loading={busy} onPress={save} />
    </Screen>
  );
}
