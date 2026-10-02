/**
 * Фон переписки. Настраивается (Профиль → «Фон чата»): узор, свой цвет или своё фото с размытием.
 * Узоры нейтральные — фигуры, точки, волны: без религиозных символов (чат открывают где угодно).
 */
import { Image } from 'expo-image';
import { StyleSheet, View } from 'react-native';
import Svg, { Circle, Defs, Path, Pattern, Rect } from 'react-native-svg';

import { useApp, type Wall } from '@/state/app';

export const WALL_PATTERNS: { key: NonNullable<Wall['pattern']>; name: string }[] = [
  { key: 'shapes', name: 'Фигуры' }, { key: 'dots', name: 'Точки' }, { key: 'waves', name: 'Волны' },
  { key: 'grid', name: 'Клетка' }, { key: 'bubbles', name: 'Круги' }, { key: 'none', name: 'Без узора' },
];
export const WALL_COLORS = ['', '#e8f0fe', '#e6f4ea', '#fef3e2', '#fde8ee', '#efe9ff', '#e3f2f1', '#dfe6ef', '#1f2937', '#0f172a'];

function isDark(hex: string) {
  const n = parseInt(hex.slice(1), 16);
  return ((n >> 16) & 255) * 0.299 + ((n >> 8) & 255) * 0.587 + (n & 255) * 0.114 < 110;
}

function Tile({ kind, stroke }: { kind: string; stroke: string }) {
  const p = { stroke, strokeWidth: 1.4, fill: 'none', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  if (kind === 'dots') return <Pattern id="w" width={24} height={24} patternUnits="userSpaceOnUse"><Circle cx={4} cy={4} r={1.3} fill={stroke} /><Circle cx={16} cy={16} r={1.3} fill={stroke} /></Pattern>;
  if (kind === 'waves') return <Pattern id="w" width={60} height={24} patternUnits="userSpaceOnUse"><Path d="M0 12c10-10 20 10 30 0s20 10 30 0" {...p} /></Pattern>;
  if (kind === 'grid') return <Pattern id="w" width={32} height={32} patternUnits="userSpaceOnUse"><Path d="M0 .7h32M.7 0v32" {...p} /></Pattern>;
  if (kind === 'bubbles') {
    return (
      <Pattern id="w" width={100} height={90} patternUnits="userSpaceOnUse">
        <Circle cx={18} cy={20} r={10} {...p} /><Circle cx={62} cy={14} r={5} {...p} /><Circle cx={78} cy={58} r={14} {...p} />
        <Circle cx={30} cy={70} r={6} {...p} /><Circle cx={52} cy={44} r={3} {...p} />
      </Pattern>
    );
  }
  return (
    <Pattern id="w" width={120} height={120} patternUnits="userSpaceOnUse">
      <Circle cx={20} cy={22} r={7} {...p} /><Path d="M70 14l8 14H62z" {...p} /><Path d="M96 60h14M103 53v14" {...p} />
      <Rect x={14} y={74} width={14} height={14} rx={3} {...p} /><Path d="M50 92c4-6 8 6 12 0s8 6 12 0" {...p} />
      <Circle cx={100} cy={102} r={3} {...p} /><Path d="M44 44l10 10M54 44L44 54" {...p} />
    </Pattern>
  );
}

export function ChatWallpaper({ wall: given }: { wall?: Wall }) {
  const app = useApp();
  const wall = given ?? app.wall;
  const { c, dark } = app;
  if (wall.photo) {
    return (
      <View style={StyleSheet.absoluteFill} pointerEvents="none">
        <Image source={{ uri: wall.photo }} style={StyleSheet.absoluteFill} contentFit="cover" blurRadius={wall.blur ?? 0} />
        <View style={[StyleSheet.absoluteFill, { backgroundColor: '#000', opacity: (wall.dim ?? 15) / 100 }]} />
      </View>
    );
  }
  const bg = wall.color || (dark ? '#10121d' : '#eceefb');
  const darkBg = wall.color ? isDark(wall.color) : dark;
  const stroke = darkBg ? 'rgba(255,255,255,0.07)' : wall.color ? 'rgba(30,35,70,0.09)' : `${c.accent}1c`;
  const pattern = wall.pattern ?? 'shapes';
  return (
    <View style={[StyleSheet.absoluteFill, { backgroundColor: bg }]} pointerEvents="none">
      {pattern !== 'none' ? (
        <Svg width="100%" height="100%">
          <Defs><Tile kind={pattern} stroke={stroke} /></Defs>
          <Rect width="100%" height="100%" fill="url(#w)" />
        </Svg>
      ) : null}
    </View>
  );
}
