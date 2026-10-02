import Constants from 'expo-constants';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, View } from 'react-native';

import { api } from '@/lib/api';
import { LANGS } from '@/lib/i18n';
import { useApp } from '@/state/app';
import { Button, Card, Chip, Divider, Field, Icon, Row, Screen, Section, Segmented, Txt } from '@/ui/kit';

export default function Settings() {
  const { c, t, lang, setLang, themeMode, setThemeMode, user, signOut, config, currency, setCurrency } = useApp();
  const [confirm, setConfirm] = useState('');
  const [deleting, setDeleting] = useState(false);

  const del = async () => {
    setDeleting(true);
    try {
      await api('/me/', { method: 'DELETE', body: { confirm } });
      await signOut();
      Alert.alert(t('Аккаунт удалён. Да вознаградит вас Аллах благом.'));
      router.replace('/');
    } catch (e: any) {
      Alert.alert(e.message);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Screen title={t('Настройки')} back>
      <Section title={t('Язык')}>
        <Card style={{ paddingVertical: 4 }}>
          {LANGS.map((l, i) => (
            <View key={l.code}>
              {i ? <Divider /> : null}
              <Row title={l.name} onPress={() => setLang(l.code)}
                right={lang === l.code ? <Icon name="checkmark-circle" color={c.accent} /> : <Icon name="ellipse-outline" color={c.line} />} />
            </View>
          ))}
        </Card>
      </Section>
      <Section title={t('Тема')}>
        <Segmented value={themeMode} onChange={setThemeMode}
          options={[{ key: 'system', label: t('Как в телефоне') }, { key: 'light', label: t('Светлая') }, { key: 'dark', label: t('Тёмная') }]} />
      </Section>
      {config?.currencies?.length ? (
        <Section title={t('Валюта')}>
          <Txt kind="small">{t('Цены остаются в валюте автора, а рядом показываем «≈» в вашей.')}</Txt>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            <Chip label={`${t('Авто')}${!currency && config.currency ? ` · ${config.currency}` : ''}`} on={!currency} onPress={() => setCurrency('')} />
            {config.currencies.map((x) => <Chip key={x.code} label={`${x.code} · ${x.name}`} on={currency === x.code} onPress={() => setCurrency(x.code)} />)}
          </View>
        </Section>
      ) : null}
      {user ? (
        <Section title={t('Удаление аккаунта')}>
          <Card style={{ gap: 10 }}>
            <Txt kind="muted">{t('Личные данные сотрутся, публикации снимутся, анкета никяха и фото удалятся. Это нельзя отменить.')}</Txt>
            <Field placeholder={t('Напишите слово «удалить»')} value={confirm} onChangeText={setConfirm} autoCapitalize="none" />
            <Button kind="danger" title={t('Удалить аккаунт')} onPress={del} loading={deleting} disabled={confirm.trim().length < 4} />
          </Card>
        </Section>
      ) : null}
      <Txt kind="small" style={{ textAlign: 'center' }}>ilm4 · {t('версия')} {Constants.expoConfig?.version ?? '1.0.0'}</Txt>
    </Screen>
  );
}
