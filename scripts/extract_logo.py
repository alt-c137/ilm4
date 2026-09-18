"""Одноразовый скрипт фазы 0: достаёт логотип (base64 PNG) из дизайн-макета.

Запуск из корня проекта: python3 scripts/extract_logo.py
Источник: /mnt/e/Adobe/ilm4/ilm4-design-C-app.html (штаб документов).
"""
import base64
import re
from pathlib import Path

SRC = Path('/mnt/e/Adobe/ilm4/ilm4-design-C-app.html')
DST = Path(__file__).resolve().parent.parent / 'static' / 'img' / 'logo.png'

html = SRC.read_text(encoding='utf-8')
match = re.search(r'data:image/png;base64,([A-Za-z0-9+/=]+)', html)
if not match:
    raise SystemExit('PNG в макете не найден')

DST.write_bytes(base64.b64decode(match.group(1)))
print(f'OK: {DST} ({DST.stat().st_size} байт)')
