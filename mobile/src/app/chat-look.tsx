import * as FileSystem from 'expo-file-system/legacy';
import * as ImagePicker from 'expo-image-picker';
import { Alert, Pressable, View } from 'react-native';

import { useApp, type Wall } from '@/state/app';
import { Button, Chip, Icon, Screen, Section, Txt } from '@/ui/kit';
import { ChatWallpaper, WALL_COLORS, WALL_PATTERNS } from '@/ui/wallpaper';

/** Фон чата — как в Telegram: узор, свой цвет или своё фото (размытие и затемнение). */
export default function ChatLook() {
  const { c, t, wall, setWall } = useApp();
  const set = (part: Partial<Wall>) => setWall({ ...wall, ...part });

  const pickPhoto = async () => {
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (r.canceled || !r.assets[0]) return;
    try {
      // копируем к себе: из временной папки системы фото может пропасть
      const to = `${FileSystem.documentDirectory}wallpaper-${Date.now()}.jpg`;
      await FileSystem.copyAsync({ from: r.assets[0].uri, to });
      if (wall.photo?.startsWith(FileSystem.documentDirectory ?? '-')) FileSystem.deleteAsync(wall.photo, { idempotent: true }).catch(() => {});
      set({ photo: to });
    } catch {
      set({ photo: r.assets[0].uri });
    }
  };
  const step = (key: 'blur' | 'dim', by: number, max: number) => set({ [key]: Math.max(0, Math.min(max, (wall[key] ?? (key === 'dim' ? 15 : 0)) + by)) });
  const stepper = (key: 'blur' | 'dim', label: string, by: number, max: number) => (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
      <Txt style={{ flex: 1, fontWeight: '600' }}>{label}</Txt>
      <Pressable onPress={() => step(key, -by, max)} hitSlop={8} style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: c.card, alignItems: 'center', justifyContent: 'center' }}><Icon name="remove" size={20} /></Pressable>
      <Txt style={{ width: 34, textAlign: 'center', fontWeight: '700' }}>{wall[key] ?? (key === 'dim' ? 15 : 0)}</Txt>
      <Pressable onPress={() => step(key, by, max)} hitSlop={8} style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: c.card, alignItems: 'center', justifyContent: 'center' }}><Icon name="add" size={20} /></Pressable>
    </View>
  );

  return (
    <Screen title={t('Фон чата')} back>
      <View style={{ height: 210, borderRadius: 22, overflow: 'hidden', justifyContent: 'flex-end', padding: 12, gap: 6, borderWidth: 1, borderColor: c.line }}>
        <ChatWallpaper />
        <View style={{ alignSelf: 'flex-start', backgroundColor: c.card, borderRadius: 18, paddingHorizontal: 12, paddingVertical: 7 }}><Txt>{t('Ассаляму алейкум!')}</Txt></View>
        <View style={{ alignSelf: 'flex-end', backgroundColor: c.accent, borderRadius: 18, paddingHorizontal: 12, paddingVertical: 7 }}><Txt color="#fff">{t('Ва алейкум ассалям')}</Txt></View>
      </View>

      <Section title={t('Узор')}>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {WALL_PATTERNS.map((p) => <Chip key={p.key} label={t(p.name)} on={!wall.photo && (wall.pattern ?? 'shapes') === p.key} onPress={() => setWall({ ...wall, pattern: p.key, photo: undefined })} />)}
        </View>
      </Section>

      <Section title={t('Цвет фона')}>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
          {WALL_COLORS.map((col) => {
            const on = !wall.photo && (wall.color ?? '') === col;
            return (
              <Pressable key={col || 'theme'} onPress={() => setWall({ ...wall, color: col, photo: undefined })} accessibilityLabel={col || t('Как в теме')}
                style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: col || c.bg, borderWidth: on ? 3 : 1, borderColor: on ? c.accent : c.line, alignItems: 'center', justifyContent: 'center' }}>
                {!col ? <Icon name="color-palette-outline" size={18} color={c.inkSoft} /> : null}
              </Pressable>
            );
          })}
        </View>
      </Section>

      <Section title={t('Своё фото')}>
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <Button kind="soft" small icon="image-outline" title={wall.photo ? t('Другое фото') : t('Выбрать фото')} onPress={pickPhoto} style={{ flex: 1 }} />
          {wall.photo ? <Button kind="ghost" small title={t('Убрать фото')} onPress={() => setWall({ ...wall, photo: undefined })} style={{ flex: 1 }} /> : null}
        </View>
        {wall.photo ? <>{stepper('blur', t('Размытие'), 4, 40)}{stepper('dim', t('Затемнение'), 5, 70)}</> : null}
      </Section>

      <Button kind="ghost" title={t('Сбросить')} onPress={() => Alert.alert(t('Вернуть обычный фон?'), undefined, [
        { text: t('Отмена'), style: 'cancel' }, { text: t('Сбросить'), onPress: () => setWall({}) }])} />
    </Screen>
  );
}
