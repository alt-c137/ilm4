/**
 * Оформление текста сообщений, как в Telegram: **жирный**, __курсив__, ~~зачёркнутый~~, `код`, ||скрытый||, ссылки.
 * Тот же разбор — на сервере (apps/chat/richtext.py) и на сайте (chat.js).
 */
import { useState } from 'react';
import { Linking, Text } from 'react-native';

import { openSiteUrl } from '@/lib/links';
import { API_URL } from '@/lib/api';

const RX = /(`[^`\n]+`)|(\*\*\S[\s\S]*?\*\*)|(__\S[\s\S]*?__)|(~~\S[\s\S]*?~~)|(\|\|\S[\s\S]*?\|\|)|(https?:\/\/[^\s<]+[^\s<.,:;!?)\]»"'])/g;

function Spoiler({ children, color }: { children: React.ReactNode; color: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Text onPress={() => setOpen(true)} suppressHighlighting
      style={open ? { backgroundColor: 'rgba(127,127,150,0.16)' } : { color: 'transparent', backgroundColor: color, opacity: 0.55 }}>{children}</Text>
  );
}

export function Rich({ text, color }: { text: string; color: string }): React.ReactNode {
  const out: React.ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const m of text.matchAll(RX)) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const [all, code, bold, italic, strike, spoiler, url] = m;
    last = m.index + all.length;
    key += 1;
    const inner = (n: number) => <Rich text={all.slice(n, -n)} color={color} />;
    if (code) out.push(<Text key={key} style={{ fontFamily: 'monospace', backgroundColor: 'rgba(127,127,160,0.2)' }}>{all.slice(1, -1)}</Text>);
    else if (bold) out.push(<Text key={key} style={{ fontWeight: '800' }}>{inner(2)}</Text>);
    else if (italic) out.push(<Text key={key} style={{ fontStyle: 'italic' }}>{inner(2)}</Text>);
    else if (strike) out.push(<Text key={key} style={{ textDecorationLine: 'line-through' }}>{inner(2)}</Text>);
    else if (spoiler) out.push(<Spoiler key={key} color={color}>{inner(2)}</Spoiler>);
    else if (url) out.push(<Text key={key} style={{ textDecorationLine: 'underline' }} onPress={() => (all.startsWith(API_URL) ? openSiteUrl(all) : Linking.openURL(all).catch(() => {}))}>{all}</Text>);
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
