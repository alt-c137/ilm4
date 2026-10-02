import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, View } from 'react-native';

import { api } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Card, Divider, Field, Icon, Row, Screen, Txt } from '@/ui/kit';

const REASONS: [string, string][] = [
  ['spam', 'Спам или реклама'], ['fraud', 'Мошенничество, просят предоплату'], ['haram', 'Харам, неприличное содержание'],
  ['fake', 'Фейк, чужие фото, обман'], ['contacts', 'Контакты в анкете / уводят в другие мессенджеры'],
  ['abuse', 'Оскорбления, угрозы'], ['other', 'Другое'],
];

/** Жалоба: модератор получает её в админке и в Telegram-группе. Автор не узнает, кто пожаловался. */
export default function Report() {
  const { type, id, user_id } = useLocalSearchParams<{ type: string; id: string; user_id?: string }>();
  const { c, t } = useApp();
  const [reason, setReason] = useState('');
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);

  const send = async () => {
    setBusy(true);
    try {
      const r = await api('/report/', { body: { type, id: Number(id), reason, text } });
      Alert.alert(t('Жалоба отправлена'), r.message);
      router.back();
    } catch (e: any) {
      Alert.alert(e.message);
    } finally {
      setBusy(false);
    }
  };
  const block = () => {
    Alert.alert(t('Заблокировать?'), t('Вы перестанете видеть друг друга, переписка закроется.'), [
      { text: t('Отмена'), style: 'cancel' },
      { text: t('Заблокировать'), style: 'destructive', onPress: async () => {
        try {
          await api('/block/', { body: { user_id: Number(user_id) } });
          router.back();
        } catch (e: any) {
          Alert.alert(e.message);
        }
      } },
    ]);
  };

  return (
    <Screen title={t('Пожаловаться')} back edges={['top', 'bottom']}>
      <Card style={{ paddingVertical: 4 }}>
        {REASONS.map(([k, label], i) => (
          <View key={k}>
            {i ? <Divider /> : null}
            <Row title={t(label)} onPress={() => setReason(k)}
              right={<Icon name={reason === k ? 'radio-button-on' : 'radio-button-off'} color={reason === k ? c.accent : c.inkSoft} />} />
          </View>
        ))}
      </Card>
      <Field placeholder={t('Подробности (по желанию)')} value={text} onChangeText={setText} multiline maxLength={500} />
      <Button title={t('Отправить жалобу')} onPress={send} disabled={!reason} loading={busy} />
      {user_id ? <Button title={t('Заблокировать')} kind="ghost" icon="ban" onPress={block} /> : null}
      <Txt kind="small" style={{ textAlign: 'center' }}>{t('Мы не сообщаем автору, кто пожаловался.')}</Txt>
    </Screen>
  );
}
