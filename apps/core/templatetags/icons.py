"""Иконки разделов с заменой на свои (без правки кода).

Как это работает: в разделе «Х» шаблон вызывает {% svc_icon 'prayer' '🕌' %}.
Если в static/img/icons/ лежит файл prayer.svg или prayer.png — показывается он,
иначе — эмодзи по умолчанию. Кладёшь свою картинку → сайт сам её подхватывает.
"""
from functools import cache
from pathlib import Path

from django import template
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.templatetags.static import static as static_url
from django.utils.html import format_html

register = template.Library()

ICONS_DIR = Path(settings.BASE_DIR) / 'static' / 'img' / 'icons'


@cache
def _icon_file(slug: str) -> str | None:
    """Найти переопределение иконки: icons/<slug>.svg|.png (dev или собранные)."""
    for ext in ('svg', 'png'):
        if (ICONS_DIR / f'{slug}.{ext}').exists():
            return f'img/icons/{slug}.{ext}'
        collected = Path(settings.STATIC_ROOT or '') / 'img' / 'icons' / f'{slug}.{ext}'
        if collected.exists():
            return f'img/icons/{slug}.{ext}'
    return None


@register.simple_tag
def svc_icon(slug: str, emoji: str = '✦', css: str = 'shero__icon') -> str:
    """Иконка раздела: своя картинка из static/img/icons/ или эмодзи."""
    rel = _icon_file(slug)
    if rel:
        url = staticfiles_storage.url(rel) if staticfiles_storage.exists(rel) else static_url(rel)
        return format_html('<div class="{}"><img src="{}" alt=""></div>', css, url)
    return format_html('<div class="{}">{}</div>', css, emoji)
