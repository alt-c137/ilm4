import { CameraView, useCameraPermissions } from 'expo-camera';
import { useRef, useState } from 'react';
import { Alert, Modal, Platform, Pressable, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, ApiError } from '@/lib/api';
import { openWeb } from '@/lib/links';
import { useApp } from '@/state/app';
import { Button, Card, Divider, Icon, Loading, Screen, Section, SetGroup, SetRow, toast, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type Row = { kind: 'web' | 'app'; id: number; title: string; ip: string; current: boolean; last: string };
type Data = { items: Row[]; twofa: boolean };

/** Достаём код входа из отсканированной ссылки вида …/accounts/qr/<код>/ */
function tokenOf(text: string) {
  const m = /\/accounts\/qr\/([A-Za-z0-9_-]{16,60})\/?/.exec(text);
  return m ? m[1] : '';
}

/**
 * «Устройства» — как в Telegram: где открыт аккаунт, завершить сеанс, подключить компьютер по QR-коду.
 * QR-код показывает страница входа на сайте; здесь его сканируют и подтверждают вход.
 */
export default function Devices() {
  const { c, t, user } = useApp();
  const { data, setData, loading, reload } = useFetch<Data>(user ? '/auth/sessions/' : null);
  const [scan, setScan] = useState(false);
  const [perm, ask] = useCameraPermissions();
  const [ask2, setAsk2] = useState<{ token: string; device: string; ip: string } | null>(null);
  const busy = useRef(false);
  if (!user) return null;

  const post = async (body: Record<string, unknown>) => {
    try {
      setData(await api<Data>('/auth/sessions/', { body }));
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const openScanner = async () => {
    if (Platform.OS === 'web') return Alert.alert(t('Сканер работает в приложении на телефоне.'));
    const ok = perm?.granted || (await ask()).granted;
    if (!ok) return Alert.alert(t('Нет доступа к камере'), t('Разрешите камеру в настройках телефона — она нужна, чтобы считать QR-код.'));
    busy.current = false;
    setScan(true);
  };
  const scanned = async (text: string) => {
    if (busy.current) return;
    const token = tokenOf(text);
    if (!token) return;
    busy.current = true;
    setScan(false);
    try {
      const info = await api<{ device: string; ip: string }>(`/auth/qr/${token}/`);
      setAsk2({ token, ...info });
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const approve = async () => {
    if (!ask2) return;
    const token = ask2.token;
    setAsk2(null);
    try {
      await api(`/auth/qr/${token}/`, { body: {} });
      toast(t('Вход подтверждён'));
      setTimeout(() => reload(true), 2500);
    } catch (e) {
      Alert.alert((e as ApiError).message);
    }
  };
  const when = (iso: string) => new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  const rows = data?.items ?? [];
  const others = rows.filter((r) => !r.current);

  return (
    <Screen title={t('Устройства')} back onRefresh={reload} refreshing={loading && !!data}>
      <Button title={t('Подключить устройство')} icon="qr-code-outline" onPress={openScanner} />
      <Txt kind="small" style={{ textAlign: 'center' }}>{t('Откройте страницу входа ilm4 на компьютере, выберите «Войти по QR-коду» и наведите на него камеру.')}</Txt>

      {!data ? (loading ? <Loading /> : null) : (
        <>
          {rows.filter((r) => r.current).map((r) => (
            <Section key={`${r.kind}${r.id}`} title={t('Это устройство')}>
              <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <Icon name="phone-portrait-outline" size={24} color={c.accent} />
                <View style={{ flex: 1 }}><Txt style={{ fontWeight: '700' }}>{r.title}</Txt><Txt kind="small">{t('сейчас')}</Txt></View>
              </Card>
            </Section>
          ))}
          {others.length ? (
            <Section title={t('Активные сеансы')}>
              <Card style={{ paddingVertical: 4 }}>
                {others.map((r, i) => (
                  <View key={`${r.kind}${r.id}`}>
                    {i ? <Divider /> : null}
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10 }}>
                      <Icon name={r.kind === 'app' ? 'phone-portrait-outline' : 'desktop-outline'} size={22} color={c.inkSoft} />
                      <View style={{ flex: 1 }}>
                        <Txt style={{ fontWeight: '700' }} numberOfLines={1}>{r.title}</Txt>
                        <Txt kind="small" numberOfLines={1}>{[r.kind === 'app' ? t('приложение') : t('сайт'), r.ip, when(r.last)].filter(Boolean).join(' · ')}</Txt>
                      </View>
                      <Button small kind="soft" title={t('Завершить')} onPress={() => post({ kind: r.kind, id: r.id })} />
                    </View>
                  </View>
                ))}
              </Card>
              <Pressable onPress={() => Alert.alert(t('Завершить все сеансы, кроме этого?'), undefined, [
                { text: t('Отмена'), style: 'cancel' }, { text: t('Завершить'), style: 'destructive', onPress: () => post({ others: true }) }])} style={{ alignItems: 'center', padding: 10 }}>
                <Txt color={c.bad} style={{ fontWeight: '700' }}>{t('Завершить все другие сеансы')}</Txt>
              </Pressable>
            </Section>
          ) : <Txt kind="muted" style={{ textAlign: 'center' }}>{t('Других сеансов нет.')}</Txt>}
          <SetGroup title={t('Защита входа')} hint={t('Потеряли телефон с приложением-аутентификатором? Напишите в поддержку — после проверки защиту снимут.')}>
            <SetRow tint="#22c55e" icon="shield-checkmark" title={t('Двухшаговая защита')}
              subtitle={data.twofa ? t('включена — при входе нужен код из приложения') : t('выключена — включить код из Google Authenticator')} onPress={() => openWeb('/accounts/2fa/')} />
          </SetGroup>
        </>
      )}

      <Modal visible={scan} animationType="slide" onRequestClose={() => setScan(false)}>
        <View style={{ flex: 1, backgroundColor: '#000' }}>
          {scan ? <CameraView style={{ flex: 1 }} facing="back" barcodeScannerSettings={{ barcodeTypes: ['qr'] }} onBarcodeScanned={(e) => scanned(e.data)} /> : null}
          <SafeAreaView style={{ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, justifyContent: 'space-between', alignItems: 'center', padding: 20 }} pointerEvents="box-none">
            <Pressable onPress={() => setScan(false)} hitSlop={12} style={{ alignSelf: 'flex-end', width: 42, height: 42, borderRadius: 21, backgroundColor: 'rgba(0,0,0,0.5)', alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="close" size={24} color="#fff" />
            </Pressable>
            <View style={{ width: 240, height: 240, borderRadius: 28, borderWidth: 3, borderColor: 'rgba(255,255,255,0.9)' }} />
            <Txt color="#fff" style={{ textAlign: 'center', backgroundColor: 'rgba(0,0,0,0.5)', borderRadius: 14, padding: 12, overflow: 'hidden' }}>{t('Наведите камеру на QR-код со страницы входа ilm4')}</Txt>
          </SafeAreaView>
        </View>
      </Modal>

      <Modal visible={!!ask2} transparent animationType="fade" onRequestClose={() => setAsk2(null)}>
        <View style={{ flex: 1, backgroundColor: c.overlay, justifyContent: 'center', padding: 22 }}>
          <View style={{ backgroundColor: c.card, borderRadius: 24, padding: 20, gap: 12 }}>
            <Txt kind="h2">{t('Войти на новом устройстве?')}</Txt>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: c.card2, borderRadius: 16, padding: 12 }}>
              <Icon name="desktop-outline" size={24} color={c.accent} />
              <View style={{ flex: 1 }}><Txt style={{ fontWeight: '700' }}>{ask2?.device}</Txt>{ask2?.ip ? <Txt kind="small">IP {ask2.ip}</Txt> : null}</View>
            </View>
            <Txt kind="muted">{t('Подтверждайте, только если вы сами сейчас открыли страницу входа ilm4 на своём компьютере. Если код вам прислали или показали другие люди — нажмите «Отмена»: так крадут аккаунты.')}</Txt>
            <Button title={t('Да, войти')} onPress={approve} />
            <Button kind="soft" title={t('Отмена')} onPress={() => setAsk2(null)} />
          </View>
        </View>
      </Modal>
    </Screen>
  );
}
