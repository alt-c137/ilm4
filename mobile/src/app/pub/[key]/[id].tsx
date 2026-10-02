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
  trip?: Trip;
};
type TripReq = { id: number; user_id?: number; name?: string; seats: number; status: string; status_name: string };
type Trip = { driver: boolean; seats: number; seats_left: number; past: boolean; my_request: TripReq | null; requests: TripReq[] };

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
  // попутчики: занять место / ответить на заявку
  const tripCall = async (path: string, body: object = {}) => {
    if (!user) return router.push('/login');
    setBusy(true);
    try {
      const r = await api<{ trip: Trip }>(path, { body });
      setData({ ...data, trip: r.trip });
    } catch (e: any) {
      Alert.alert(e.message);
    } finally {
      setBusy(false);
    }
  };
  const book = () => {
    const left = data.trip?.seats_left ?? 0;
    if (left <= 1) return tripCall(`/trips/${id}/request/`, { seats: 1 });
    Alert.alert(t('Сколько мест?'), undefined, [
      ...Array.from({ length: Math.min(left, 4) }, (_x, i) => ({ text: String(i + 1), onPress: () => tripCall(`/trips/${id}/request/`, { seats: i + 1 }) })),
      { text: t('Отмена'), style: 'cancel' as const },
    ]);
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

      {data.trip && !data.trip.past ? <TripBlock trip={data.trip} mine={data.mine} busy={busy} onBook={book} onAct={(rid, a) => tripCall(`/trips/request/${rid}/${a}/`)} /> : null}

      <View style={{ gap: 10 }}>
        {data.can_message ? <Button kind={data.trip?.driver && !data.trip.my_request ? 'soft' : 'primary'} title={t('Написать автору')} icon="chatbubble-ellipses" onPress={message} loading={busy} /> : null}
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

/** Попутчики: свободные места, моя заявка или заявки ко мне (водителю). */
function TripBlock({ trip, mine, busy, onBook, onAct }: { trip: Trip; mine: boolean; busy: boolean; onBook: () => void;
  onAct: (id: number, action: 'accept' | 'decline' | 'cancel') => void }) {
  const { c, t } = useApp();
  if (!trip.driver) return null;
  if (mine) {
    return (
      <Card style={{ gap: 10 }}>
        <Txt kind="h3">{t('Заявки на места')} · {t('свободно {n} из {m}', { n: trip.seats_left, m: trip.seats })}</Txt>
        {trip.requests.length ? trip.requests.map((r) => (
          <View key={r.id} style={{ gap: 8, paddingVertical: 6, borderTopWidth: 0.5, borderTopColor: c.line }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Txt style={{ flex: 1, fontWeight: '700' }}>{r.name}</Txt>
              <Txt kind="small">{t('мест: {n}', { n: r.seats })} · {r.status_name}</Txt>
            </View>
            {r.status === 'pending' ? (
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <Button small title={t('Взять')} onPress={() => onAct(r.id, 'accept')} loading={busy} style={{ flex: 1 }} />
                <Button small kind="ghost" title={t('Отказать')} onPress={() => onAct(r.id, 'decline')} style={{ flex: 1 }} />
              </View>
            ) : null}
          </View>
        )) : <Txt kind="muted">{t('Заявок пока нет. Когда кто-то попросит место, придёт уведомление.')}</Txt>}
      </Card>
    );
  }
  const my = trip.my_request;
  if (my?.status === 'accepted') {
    return (
      <Card soft style={{ gap: 10 }}>
        <Txt kind="h3" color={c.ok}>✓ {t('Место за вами')}: {my.seats}</Txt>
        <Button kind="ghost" title={t('Не смогу поехать')} onPress={() => onAct(my.id, 'cancel')} loading={busy} />
      </Card>
    );
  }
  if (my?.status === 'pending') {
    return (
      <Card soft style={{ gap: 10 }}>
        <Txt style={{ fontWeight: '700' }}>{t('Заявка отправлена — ждём ответа водителя.')}</Txt>
        <Button kind="ghost" title={t('Отменить заявку')} onPress={() => onAct(my.id, 'cancel')} loading={busy} />
      </Card>
    );
  }
  if (!trip.seats_left) return <Card soft><Txt kind="muted">{t('Свободных мест нет — напишите водителю, вдруг кто-то откажется.')}</Txt></Card>;
  return <Button title={t('Занять место')} icon="checkmark-circle" onPress={onBook} loading={busy} />;
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
