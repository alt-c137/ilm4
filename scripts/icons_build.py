"""Собрать значки интерфейса из набора Lucide (лицензия ISC — можно в коммерческом проекте).

    npm pack lucide-static && tar xzf lucide-static-*.tgz          # один раз, в любой временной папке
    python3 scripts/icons_build.py <папка>/package/icons

Пишет apps/core/icons_lucide.py — словарь {имя: содержимое <svg>} для тега {% ico 'имя' %}.
Нужен новый значок — добавь его имя в NAMES (имена как на lucide.dev) и запусти снова.
Эмодзи вместо значков в интерфейсе не используем (см. ЧТО_ДОДЕЛАТЬ.md, v50).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# имя у нас: имя в Lucide
NAMES = {
    # привычки и трекер
    'h-check': 'check', 'h-pill': 'pill', 'h-water': 'droplet', 'h-quran': 'book-open', 'h-mosque': 'mosque', 'h-dua': 'hand-heart',
    'h-walk': 'footprints', 'h-sport': 'dumbbell', 'h-sleep': 'bed', 'h-lang': 'languages', 'h-books': 'library',
    'h-nophone': 'phone-off', 'h-moon': 'moon', 'h-sun': 'sun', 'h-sunrise': 'sunrise', 'h-sunset': 'sunset', 'h-target': 'target',
    'h-together': 'handshake', 'h-heart': 'heart', 'h-star': 'star', 'h-write': 'pen-line', 'h-speak': 'mic', 'h-work': 'briefcase',
    'h-clean': 'paintbrush', 'h-money': 'coins', 'h-food': 'salad', 'h-run': 'activity', 'h-mind': 'brain', 'h-coffee': 'coffee',
    'h-study': 'graduation-cap', 'h-leaf': 'leaf', 'h-timer': 'timer', 'h-bike': 'bike', 'h-apple': 'apple', 'h-idea': 'lightbulb',
    'h-list': 'list-checks', 'h-home': 'house', 'h-family': 'users', 'h-meet': 'calendar-days',
    'flame': 'flame', 'alarm': 'alarm-clock', 'note': 'notebook-pen', 'trophy': 'trophy', 'medal': 'medal', 'award': 'award',
    'hourglass': 'hourglass', 'target': 'target', 'sunrise': 'sunrise', 'sun': 'sun', 'moon': 'moon', 'handshake': 'handshake',
    # карта и разделы
    'mosque': 'mosque', 'cafe': 'utensils', 'shop': 'shopping-bag', 'butcher': 'beef', 'hotel': 'hotel', 'place': 'map-pin',
    'cart': 'shopping-cart', 'steth': 'stethoscope', 'dove': 'bird', 'truck': 'truck', 'car': 'car', 'doc': 'file-text',
    'wallet': 'wallet', 'books': 'library', 'smartphone': 'smartphone', 'flag': 'flag', 'ban': 'ban', 'cloud': 'cloud',
    'package': 'package', 'warn': 'triangle-alert', 'okcircle': 'circle-check-big', 'xcircle': 'circle-x', 'scale': 'scale',
    # помощник, лента, сообщества
    'bot': 'bot', 'sparkles': 'sparkles', 'gift': 'gift', 'film': 'clapperboard', 'story': 'circle-dashed', 'feed': 'rss',
    'dashboard': 'layout-dashboard', 'kanban': 'square-kanban', 'hash': 'hash', 'voice': 'volume-2', 'crown': 'crown',
    'shieldcheck': 'shield-check', 'terminal': 'terminal', 'key': 'key-round', 'mask': 'venetian-mask', 'idcard': 'id-card',
    'compass': 'compass', 'community': 'users-round', 'settings': 'settings-2', 'login': 'log-in', 'userplus': 'user-plus',
    'headphones': 'headphones', 'clipboard': 'clipboard-list', 'idea': 'lightbulb',
    # редактор фото
    'undo': 'undo-2', 'redo': 'redo-2', 'crop': 'crop', 'adjust': 'sliders-horizontal', 'bright': 'sun-medium', 'contrast': 'contrast',
    'palette': 'palette', 'type': 'type', 'pencil': 'pencil', 'eraser': 'eraser', 'flip': 'flip-horizontal-2', 'rotate': 'rotate-ccw-square',
    'wand': 'wand-sparkles', 'warmth': 'thermometer-sun', 'fade': 'blend', 'vignette': 'aperture', 'sharpen': 'triangle', 'grain': 'sparkle',
    'marker': 'highlighter', 'move': 'move', 'ratio': 'ratio', 'shadows': 'sun-dim', 'saturation': 'droplets', 'blur': 'droplet-off',
}


def inner(path: Path) -> str:
    text = path.read_text()
    body = text[text.index('>', text.index('<svg')) + 1:text.rindex('</svg>')]
    return re.sub(r'\s+', ' ', body).replace('> <', '><').replace(' />', '/>').strip()


def main(src: str) -> None:
    src = Path(src)
    out = ['"""Значки из набора Lucide (ISC License, © Lucide Contributors). Файл собран scripts/icons_build.py — руками не править."""',
           'LUCIDE = {']
    for name, lucide in sorted(NAMES.items()):
        file = src / f'{lucide}.svg'
        if not file.exists():
            sys.exit(f'нет значка {lucide}')
        out.append(f'    {name!r}: {inner(file)!r},')
    out.append('}')
    (ROOT / 'apps' / 'core' / 'icons_lucide.py').write_text('\n'.join(out) + '\n')
    print(f'значков: {len(NAMES)}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '')
