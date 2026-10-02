import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Alert, KeyboardAvoidingView, Linking, Platform, Pressable, View } from 'react-native';

import { api, ApiError } from '@/lib/api';
import { useApp } from '@/state/app';
import { Button, Divider, Field, Icon, Screen, Segmented, Txt } from '@/ui/kit';

export default function Login() {
  const { c, t, signIn, config, lang } = useApp();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [tgWaiting, setTgWaiting] = useState(false);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (poll.current) clearInterval(poll.current); }, []);

  const done = async (r: any) => {
    await signIn(r.token, r.user);
    router.back();
  };

  const submit = async () => {
    setBusy(true);
    setErrors({});
    try {
      const r = mode === 'login'
        ? await api('/auth/login/', { body: { login: email.trim(), password, device: Platform.OS } })
        : await api('/auth/register/', { body: { email: email.trim(), password, name: name.trim(), language: lang, device: Platform.OS } });
      await done(r);
    } catch (e) {
      const err = e as ApiError;
      if (err.fields && Object.keys(err.fields).length) setErrors(err.fields);
      else setErrors({ all: err.message });
    } finally {
      setBusy(false);
    }
  };

  const telegram = async () => {
    try {
      const r = await api('/auth/telegram/start/', { body: {} });
      setTgWaiting(true);
      await Linking.openURL(r.url);
      if (poll.current) clearInterval(poll.current);
      const started = Date.now();
      poll.current = setInterval(async () => {
        if (Date.now() - started > 10 * 60000) {
          clearInterval(poll.current!);
          setTgWaiting(false);
          return;
        }
        try {
          const p = await api('/auth/telegram/poll/', { body: { nonce: r.nonce } });
          if (p.status === 'ok') {
            clearInterval(poll.current!);
            setTgWaiting(false);
            await done(p);
          }
        } catch (e) {
          if ((e as ApiError).status === 410) {
            clearInterval(poll.current!);
            setTgWaiting(false);
          }
        }
      }, 2000);
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };

  const reset = async () => {
    if (!email.includes('@')) {
      setErrors({ email: t('Впишите email — пришлём ссылку для нового пароля.') });
      return;
    }
    await api('/auth/password-reset/', { body: { email: email.trim() } }).catch(() => {});
    Alert.alert(t('Проверьте почту'), t('Если такой email зарегистрирован, мы отправили ссылку для нового пароля.'));
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen title={mode === 'login' ? t('Вход') : t('Регистрация')} right={
        <Pressable onPress={() => router.back()} hitSlop={10}><Icon name="close" size={26} color={c.inkSoft} /></Pressable>}>
        <Txt kind="muted">{t('Один аккаунт для приложения, сайта и Telegram-бота ilm4.')}</Txt>
        {config?.features.telegram_login !== false ? (
          <>
            <Button title={tgWaiting ? t('Ждём подтверждения в Telegram…') : t('Войти через Telegram')} icon="paper-plane" onPress={telegram}
              style={{ backgroundColor: '#229ED9' }} />
            {tgWaiting ? <Txt kind="small" style={{ textAlign: 'center' }}>{t('В боте нажмите «📱 Войти и отправить мой номер» и вернитесь сюда.')}</Txt> : null}
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ flex: 1 }}><Divider /></View><Txt kind="small">{t('или')}</Txt><View style={{ flex: 1 }}><Divider /></View>
            </View>
          </>
        ) : null}
        <Segmented value={mode} onChange={(m) => { setMode(m); setErrors({}); }}
          options={[{ key: 'login', label: t('Вход') }, { key: 'register', label: t('Регистрация') }]} />
        {mode === 'register' ? <Field label={t('Имя')} value={name} onChangeText={setName} autoComplete="name" error={errors.first_name} /> : null}
        <Field label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email"
          error={errors.email} />
        <Field label={t('Пароль')} value={password} onChangeText={setPassword} secureTextEntry autoComplete={mode === 'login' ? 'password' : 'new-password'}
          error={errors.password2 || errors.password1} onSubmitEditing={submit} />
        {errors.all ? <Txt color={c.bad}>{errors.all}</Txt> : null}
        <Button title={mode === 'login' ? t('Войти') : t('Создать аккаунт')} onPress={submit} loading={busy} disabled={!email || !password} />
        {mode === 'login' ? <Button kind="ghost" title={t('Забыли пароль?')} onPress={reset} style={{ borderWidth: 0 }} /> : (
          <Txt kind="small" style={{ textAlign: 'center' }}>{t('Регистрируясь, вы принимаете правила ilm4 и политику конфиденциальности.')}</Txt>
        )}
      </Screen>
    </KeyboardAvoidingView>
  );
}
