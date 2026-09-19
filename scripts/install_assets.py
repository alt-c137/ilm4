# Установка ассетов Исы: выбор подходящих SVG и баннеров, системные имена.
import shutil
from pathlib import Path

SRC = Path('/mnt/e/Adobe/ilm4')
ICONS_SRC = SRC / 'icons'
ICONS_DST = Path('static/img/icons')
BAN_SRC = SRC / 'Картинки'
BAN_DST = Path('static/img/banner')

ICONS_DST.mkdir(parents=True, exist_ok=True)
BAN_DST.mkdir(parents=True, exist_ok=True)

# разделы: ключ → выбранный файл (по смыслу)
sections = {
    'prayer': 'ipray-svgrepo-com.svg',
    'buy': 'buy-cart-online-svgrepo-com.svg',
    'map': 'map-svgrepo-com.svg',
    'health': 'health-svgrepo-com.svg',
    'nikah': 'marriage-svgrepo-com.svg',
    'forum': 'forum-svgrepo-com.svg',
    'news': 'news-publishing-svgrepo-com.svg',
    'jobs': 'looking-for-job-svgrepo-com.svg',
    'migration': 'move-svgrepo-com.svg',
    'services': 'magic-stick-svgrepo-com.svg',
    'library': 'library-svgrepo-com.svg',
    'chat': 'chat-round-line-svgrepo-com.svg',
    'wallet': 'wallet-money-svgrepo-com.svg',
}

# категории ilmbuy
cats = {
    'cat-electronics': 'electronics-svgrepo-com.svg',
    'cat-auto': 'car-svgrepo-com.svg',
    'cat-clothes': 'clothes-svgrepo-com.svg',
    'cat-home': 'home-1-svgrepo-com.svg',
    'cat-kids': 'kids-couple-svgrepo-com.svg',
    'cat-food': 'food-dish-svgrepo-com.svg',
    'cat-services': 'salesman-salesman-svgrepo-com.svg',
    'cat-books': 'books-14-svgrepo-com.svg',
    'cat-other': 'other-1-svgrepo-com.svg',
}

count = 0
for key, fname in {**sections, **cats}.items():
    src = ICONS_SRC / fname
    if not src.exists():
        print('НЕТ ИСХОДНИКА:', key, fname)
        continue
    shutil.copy(src, ICONS_DST / f'{key}.svg')
    count += 1
print(f'иконок установлено: {count}')

# баннеры: как есть, PNG
banners = {'halal-market.png': 'buy.png', 'prayer.png': 'prayer.png', 'nikah.png': 'nikah.png'}
for src_name, dst_name in banners.items():
    src = BAN_SRC / src_name
    if src.exists():
        shutil.copy(src, BAN_DST / dst_name)
        print('баннер:', dst_name, src.stat().st_size // 1024, 'КБ')
    else:
        print('НЕТ БАННЕРА:', src_name)
