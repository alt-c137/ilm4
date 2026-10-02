import * as Clipboard from 'expo-clipboard';
import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Linking, Platform, Pressable, Share, View } from 'react-native';

import { api } from '@/lib/api';
import { shortDate } from '@/lib/hijri';
import { useApp } from '@/state/app';
import { Button, Card, Divider, ErrorBox, Field, Icon, Loading, Screen, Txt } from '@/ui/kit';
import { useFetch } from '@/ui/useFetch';

type Detail = {
  id: number; title: string; subtitle: string; image: string; created_at: string; text: string;
  fields: { label: string; value: string }[]; contact: string; owner: { id: number; name: string } | null;
  mine: boolean; can_message: boolean; url: string; lat: number | null; lon: number | null; verified: boolean;
  replies?: { id: number; text: string; author: string; created_at: string }[]; features?: string[];
};

export default function PubDetail() {
  const { key, id } = useLocalSearchParams<{ key: string; id: string }>();
  const { c, t, user } = useApp();
  const { data, loading, error, reload, setData } = useFetch<Detail>(`/pubs/${key}/${id}/`);
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState('');

  if (!data) return <Screen back title="">{loading ? <Loading /> : <ErrorBox error={error?.message ?? ''} onRetry={reload} />}</Screen>;

  const phone = /^[+\d][\d\s()-]{6,}$/.test(data.contact.trim()) ? data.contact.replace(/[^\d+]/g, '') : '';
  const message = async () => {
    if (!user) return router.push('/login');
    setBusy(true);
    try {
      const r = await api(`/pubs/${key}/${id}/message/`, { body: {} });
      router.push(`/chat/${r.thread_id}`);
    } catch (e: any) {
      Alert.alert(e.message);
    } finally {
      setBusy(false);
    }
  };
  const openMap = () => {
    const q = `${data.lat},${data.lon}`;
    Linking.openURL(Platform.OS === 'ios' ? `http://maps.apple.com/?ll=${q}&q=${encodeURIComponent(data.title)}` : `geo:${q}?q=${q}(${encodeURIComponent(data.title)})`);
  };
  const sendReply = async () => {
    if (!user) return router.push('/login');
    try {
      const r = await api(`/forum/${id}/reply/`, { body: { text: reply } });
      setData({ ...data, replies: [...(data.replies ?? []), r] });
      setReply('');
    } catch (e: any) {
      Alert.alert(e.message);
    }
  };

  return (
    <Screen back title={t('Подробнее')} onRefresh={reload} refreshing={loading} right={
      <View style={{ flexDirection: 'row', gap: 16 }}>
        {data.url ? <Pressable onPress={() => Share.share({ message: `${data.title}\n${data.url}` })} hitSlop={8}><Icon name="share-outline" color={c.accent} /></Pressable> : null}
        {!data.mine ? <Pressable onPress={() => (user ? router.push({ pathname: '/report', params: { type: key, id: String(id) } }) : router.push('/login'))} hitSlop={8}>
          <Icon name="flag-outline" color={c.inkSoft} /></Pressable> : null}
      </View>}>
      {data.image ? <Image source={{ uri: data.image }} style={{ width: '100%', aspectRatio: 4 / 3, borderRadius: 22, backgroundColor: c.card2 }} contentFit="cover" /> : null}
      <View style={{ gap: 6 }}>
        <Txt kind="h1" selectable>{data.title}{data.verified ? ' ✓' : ''}</Txt>
        {data.subtitle ? <Txt kind="h3" color={c.accentD}>{data.subtitle}</Txt> : null}
        <Txt kind="small">{shortDate(data.created_at)}{data.owner ? ` · ${data.owner.name}` : ''}</Txt>
      </View>

      {data.fields.length ? (
        <Card style={{ paddingVertical: 4 }}>
          {data.fields.map((f, i) => (
            <View key={f.label}>
              {i ? <Divider /> : null}
              <View style={{ flexDirection: 'row', paddingVertical: 11, gap: 12 }}>
                <Txt kind="muted" style={{ width: 120 }}>{f.label}</Txt>
                <Txt style={{ flex: 1, fontWeight: '600' }} selectable>{f.value}</Txt>
              </View>
            </View>
          ))}
        </Card>
      ) : null}

      {data.features?.length ? (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {data.features.map((f) => <View key={f} style={{ backgroundColor: c.accentSoft, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6 }}><Txt kind="small" color={c.accentD}>{f}</Txt></View>)}
        </View>
      ) : null}

      {data.text ? <Card><Txt selectable>{data.text}</Txt></Card> : null}

      <View style={{ gap: 10 }}>
        {data.can_message ? <Button title={t('Написать автору')} icon="chatbubble-ellipses" onPress={message} loading={busy} /> : null}
        {phone ? <Button kind="soft" title={t('Позвонить: {n}', { n: data.contact })} icon="call" onPress={() => Linking.openURL(`tel:${phone}`)} /> : null}
        {data.contact && !phone ? (
          <Button kind="soft" title={data.contact} icon="copy-outline" onPress={async () => { await Clipboard.setStringAsync(data.contact); Alert.alert(t('Скопировано')); }} />
        ) : null}
        {data.lat !== null && data.lon !== null ? <Button kind="ghost" title={t('Открыть на карте')} icon="map" onPress={openMap} /> : null}
      </View>

      {data.replies ? (
        <View style={{ gap: 10 }}>
          <Txt kind="label">{t('Ответы')} · {data.replies.length}</Txt>
          {data.replies.map((r) => (
            <Card key={r.id} soft style={{ gap: 4 }}>
              <Txt kind="small" style={{ fontWeight: '700', color: c.ink }}>{r.author} · {shortDate(r.created_at)}</Txt>
              <Txt selectable>{r.text}</Txt>
            </Card>
          ))}
          <ReplyBox value={reply} onChange={setReply} onSend={sendReply} />
        </View>
      ) : null}
      <Txt kind="small" style={{ textAlign: 'center' }}>{t('ilm4 — площадка для объявлений. За товары и услуги отвечают авторы. Не переводите предоплату незнакомцам.')}</Txt>
    </Screen>
  );
}

function ReplyBox({ value, onChange, onSend }: { value: string; onChange: (s: string) => void; onSend: () => void }) {
  const { t } = useApp();
  return (
    <View style={{ gap: 8 }}>
      <Field placeholder={t('Ваш ответ')} value={value} onChangeText={onChange} multiline />
      <Button title={t('Ответить')} onPress={onSend} disabled={value.trim().length < 2} />
    </View>
  );
}
