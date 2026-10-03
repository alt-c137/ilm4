/**
 * Просмотр фото на весь экран — как в Telegram: листание пальцем, счётчик «2 из 5», смахнул вниз — закрыл.
 * Используется для фото профиля (история аватарок), картинки группы и фото в переписке.
 */
import { Image } from 'expo-image';
import { useRef, useState } from 'react';
import { FlatList, Modal, Pressable, Text, useWindowDimensions, View } from 'react-native';
import { Gesture, GestureDetector, GestureHandlerRootView } from 'react-native-gesture-handler';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Icon } from './kit';

export type Photo = { url: string; id?: number; date?: string; name?: string };
export type PhotoAction = { title: string; danger?: boolean; onPress: (photo: Photo, index: number) => void; show?: (index: number) => boolean };

export function PhotoViewer({ photos, index, onClose, title, headers, actions }: {
  photos: Photo[]; index: number | null; onClose: () => void; title?: string;
  headers?: Record<string, string>; actions?: PhotoAction[];
}) {
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const [at, setAt] = useState(0);
  const [seenIndex, setSeenIndex] = useState<number | null>(null);
  const list = useRef<FlatList<Photo>>(null);
  const dy = useSharedValue(0);
  const open = index !== null && photos.length > 0;
  if (index !== seenIndex) {            // открыли заново — начинаем с выбранного фото
    setSeenIndex(index);
    if (index !== null) setAt(Math.min(index, Math.max(0, photos.length - 1)));
  }

  // смахнул вниз — закрыть (как в Telegram)
  const swipe = Gesture.Pan().activeOffsetY([-18, 18]).failOffsetX([-24, 24]).runOnJS(true)
    .onUpdate((e) => { dy.value = e.translationY; })
    .onEnd((e) => {
      if (Math.abs(e.translationY) > 120) { onClose(); dy.value = 0; } else dy.value = withTiming(0, { duration: 160 });
    });
  const moved = useAnimatedStyle(() => ({
    transform: [{ translateY: dy.value }, { scale: Math.max(0.75, 1 - Math.abs(dy.value) / 1400) }],
    opacity: Math.max(0.35, 1 - Math.abs(dy.value) / 520),
  }));

  if (!open) return null;
  const cur = photos[Math.min(at, photos.length - 1)];
  const shown = (actions ?? []).filter((a) => !a.show || a.show(at));
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose} statusBarTranslucent>
      {/* окно Modal — отдельный корень: жестам нужен свой GestureHandlerRootView */}
      <GestureHandlerRootView style={{ flex: 1, backgroundColor: '#05060b' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingTop: insets.top + 6, paddingHorizontal: 10, paddingBottom: 6 }}>
          <Pressable onPress={onClose} hitSlop={10} accessibilityLabel="close"
            style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(255,255,255,0.1)', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="close" size={24} color="#fff" />
          </Pressable>
          <View style={{ flex: 1, alignItems: 'center' }}>
            {title || cur?.name ? <Text style={{ color: '#fff', fontSize: 15.5, fontWeight: '700' }} numberOfLines={1}>{cur?.name || title}</Text> : null}
            <Text style={{ color: 'rgba(255,255,255,0.65)', fontSize: 12.5 }}>
              {[photos.length > 1 ? `${at + 1} / ${photos.length}` : '', cur?.date ?? ''].filter(Boolean).join(' · ')}
            </Text>
          </View>
          <View style={{ width: 44 }} />
        </View>
        <GestureDetector gesture={swipe}>
          <Animated.View style={[{ flex: 1 }, moved]}>
            <FlatList
              ref={list} data={photos} horizontal pagingEnabled showsHorizontalScrollIndicator={false}
              keyExtractor={(p, i) => `${p.id ?? i}:${p.url}`}
              initialScrollIndex={Math.min(index ?? 0, photos.length - 1)}
              getItemLayout={(_d, i) => ({ length: width, offset: width * i, index: i })}
              onMomentumScrollEnd={(e) => setAt(Math.round(e.nativeEvent.contentOffset.x / width))}
              renderItem={({ item }) => (
                <View style={{ width, height: height - insets.top - 150, alignItems: 'center', justifyContent: 'center' }}>
                  <Image source={{ uri: item.url, headers }} style={{ width, height: '100%' }} contentFit="contain" transition={120} />
                </View>
              )}
            />
          </Animated.View>
        </GestureDetector>
        {photos.length > 1 && photos.length <= 30 ? (
          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 5, paddingVertical: 8 }}>
            {photos.map((p, i) => <View key={`${p.id ?? i}`} style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: i === at ? '#fff' : 'rgba(255,255,255,0.3)' }} />)}
          </View>
        ) : null}
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 8, paddingHorizontal: 16, paddingBottom: insets.bottom + 14, minHeight: 20 }}>
          {shown.map((a) => (
            <Pressable key={a.title} onPress={() => cur && a.onPress(cur, at)}
              style={{ borderRadius: 999, paddingVertical: 11, paddingHorizontal: 18, backgroundColor: 'rgba(255,255,255,0.14)' }}>
              <Text style={{ color: a.danger ? '#ff8a80' : '#fff', fontSize: 14.5, fontWeight: '700' }}>{a.title}</Text>
            </Pressable>
          ))}
        </View>
      </GestureHandlerRootView>
    </Modal>
  );
}
