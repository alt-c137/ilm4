import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, Switch, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, Field, Icon, Screen, Section, Txt } from '@/ui/kit';
import { HabitIcon, ICONS } from '@/ui/tracker';

/** Новый общий трекер: привычки одни на всех, отметки у каждого свои. */
export default function BoardNew() {
  const { c, t } = useApp();
  const [title, setTitle] = useState('');
  const [emoji, setEmoji] = useState('h-together');
  const [compete, setCompete] = useState(false);
  const [busy, setBusy] = useState(false);
  const create = async () => {
    setBusy(true);
    try {
      const r = await api<{ id: number }>('/tracker/boards/new/', { body: { title, emoji, compete: compete ? '1' : '' } });
      router.replace(`/habits/board/${r.id}`);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen back title={t('Общий трекер')}>
      <Txt kind="muted">{t('Привычки одни на всех — отметки у каждого свои. Людей позовёте ссылкой.')}</Txt>
      <Field label={t('Название')} value={title} onChangeText={setTitle} maxLength={80} placeholder={t('Например: Учим арабский')} autoFocus />
      <Section title={t('Значок')}>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {['h-together', ...ICONS.slice(1)].map((e) => (
            <Pressable key={e} onPress={() => setEmoji(e)} style={{ width: 42, height: 42, borderRadius: 13, alignItems: 'center', justifyContent: 'center',
              backgroundColor: emoji === e ? c.accentSoft : c.card, borderWidth: 2, borderColor: emoji === e ? c.accent : 'transparent' }}>
              <HabitIcon value={e} size={22} color={emoji === e ? c.accentD : c.ink} />
            </Pressable>
          ))}
        </View>
      </Section>
      <Card soft style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ flex: 1 }}>
          <Txt style={{ fontWeight: '700' }}><Icon name="trophy" size={15} color="#eab308" /> {t('Соревнование')}</Txt>
          <Txt kind="small">{t('Таблица: кто сколько выполнил. Можно включить позже.')}</Txt>
        </View>
        <Switch value={compete} onValueChange={setCompete} trackColor={{ true: c.accent, false: c.line }} />
      </Card>
      <Button title={t('Создать')} onPress={create} loading={busy} disabled={title.trim().length < 2} />
    </Screen>
  );
}
