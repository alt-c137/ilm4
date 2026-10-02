/** Цвета — те же, что на сайте ilm4 (static/css/tokens.css), светлая и тёмная тема. */
export const palettes = {
  light: {
    accent: '#6d5efc', accentD: '#584be6', accentSoft: '#ecebff',
    bg: '#f2f3fb', card: '#ffffff', card2: '#f6f7fc', ink: '#15172a', inkSoft: '#6a6e82', line: '#eceef5',
    ok: '#12a150', bad: '#e5484d', warn: '#d97706', onAccent: '#ffffff', overlay: 'rgba(12,14,30,0.45)',
  },
  dark: {
    accent: '#7c6ffd', accentD: '#9d93ff', accentSoft: '#241f45',
    bg: '#0e1016', card: '#171a24', card2: '#1c2030', ink: '#eceef7', inkSoft: '#9aa0b4', line: '#262b3a',
    ok: '#34d399', bad: '#f87171', warn: '#fbbf24', onAccent: '#ffffff', overlay: 'rgba(0,0,0,0.6)',
  },
};
export type Colors = typeof palettes.light;

export const radius = { s: 12, m: 16, l: 22, xl: 28, pill: 999 };
export const space = (n: number) => n * 4;
