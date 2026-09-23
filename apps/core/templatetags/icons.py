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
from django.utils.safestring import mark_safe

register = template.Library()

ICONS_DIR = Path(settings.BASE_DIR) / 'static' / 'img' / 'icons'
BANNERS_DIR = Path(settings.BASE_DIR) / 'static' / 'img' / 'banner'


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


@register.simple_tag
def svc_glyph(slug: str, emoji: str = '✦', css: str = 'glyph') -> str:
    """Иконка раздела маской: цвет задаёт CSS (currentColor) — единый стиль
    и автоподстройка под тему. Нет файла — эмодзи-фоллбек."""
    rel = _icon_file(slug)
    if rel:
        url = staticfiles_storage.url(rel) if staticfiles_storage.exists(rel) else static_url(rel)
        return format_html('<span class="{}" style="--ic:url(\'{}\')" aria-hidden="true"></span>', css, url)
    return format_html('<span class="{} glyph--emoji" aria-hidden="true">{}</span>', css, emoji)


# Линейные иконки интерфейса (24×24, stroke = currentColor) — {% ico 'pin' %}
UI_ICONS = {
    'back': '<path d="M15 5l-7 7 7 7"/>',
    'search': '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4-4"/>',
    'grid': '<rect x="4" y="4" width="6.5" height="6.5" rx="2"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="2"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="2"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="3.25"/>',
    'home': '<path d="M3.5 10.5 12 3.5l8.5 7V19a1.5 1.5 0 0 1-1.5 1.5h-4v-6h-6v6H5A1.5 1.5 0 0 1 3.5 19z"/>',
    'pin': '<path d="M12 21s-6-5.3-6-10a6 6 0 0 1 12 0c0 4.7-6 10-6 10z"/><circle cx="12" cy="11" r="2.2"/>',
    'calendar': '<rect x="3.5" y="5" width="17" height="15" rx="2.5"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/>',
    'clock': '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    'eye': '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    'chat': '<path d="M20.5 11.5a8 8 0 0 1-11.4 7.2L3.5 20.5l1.8-5.5a8 8 0 1 1 15.2-3.5z"/>',
    'phone': '<path d="M6.5 3.5h3l1.5 4-2 1.5a12 12 0 0 0 6 6l1.5-2 4 1.5v3a2 2 0 0 1-2.2 2A16.5 16.5 0 0 1 4.5 5.7 2 2 0 0 1 6.5 3.5z"/>',
    'globe': '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.6 3.6 5.4 3.6 8.5s-1.1 5.9-3.6 8.5c-2.5-2.6-3.6-5.4-3.6-8.5S9.5 6.1 12 3.5z"/>',
    'shield': '<path d="M12 3l7.5 3v5.5c0 4.6-3.2 8.2-7.5 9.5-4.3-1.3-7.5-4.9-7.5-9.5V6z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
    'info': '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8h.01"/>',
    'building': '<path d="M4.5 20.5V5a1.5 1.5 0 0 1 1.5-1.5h8A1.5 1.5 0 0 1 15.5 5v15.5M15.5 9.5H18a1.5 1.5 0 0 1 1.5 1.5v9.5M3 20.5h18M8 7.5h4M8 11h4M8 14.5h4"/>',
    'briefcase': '<rect x="3.5" y="7" width="17" height="12.5" rx="2.5"/><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7M3.5 12.5h17"/>',
    'star': '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8L3.5 9.7l5.9-.9z"/>',
    'user': '<circle cx="12" cy="8" r="4"/><path d="M4.5 20.5c1.2-3.6 4.1-5.5 7.5-5.5s6.3 1.9 7.5 5.5"/>',
    'heart': '<path d="M12 20s-7-4.5-7-9.5A3.8 3.8 0 0 1 12 8a3.8 3.8 0 0 1 7 2.5C19 15.5 12 20 12 20z"/>',
    'pulse': '<path d="M12 20s-7-4.5-7-9.5A3.8 3.8 0 0 1 12 8a3.8 3.8 0 0 1 7 2.5C19 15.5 12 20 12 20z"/><path d="M5.5 12H9l1.5-2.5 2 4L14 12h4.5"/>',
    'arrow': '<path d="M5 12h14M13 6l6 6-6 6"/>',
    'send': '<path d="M4 12l16-8-6 16-2.5-6.5z"/><path d="M11.5 13.5 20 4"/>',
    'edit': '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    'plus': '<path d="M12 5v14M5 12h14"/>',
    'tag': '<path d="M3.5 12.5V4.5a1 1 0 0 1 1-1h8l8 8-9 9z"/><circle cx="8" cy="8" r="1.5"/>',
    'news': '<path d="M4 5h13v14H5a1 1 0 0 1-1-1V5zM17 8h3v9a2 2 0 0 1-2 2M7 8h7M7 11.5h7M7 15h5"/>',
    'plane': '<path d="M10.5 13.5 3 11l1.5-1.5L10 10l4.5-4.5c.6-.6 1.6-.6 2.1 0 .6.6.6 1.6 0 2.1L12 12l.5 5.5L11 19l-2.5-7.5z"/>',
    'rings': '<circle cx="9" cy="14" r="5"/><circle cx="15" cy="14" r="5"/><path d="M10 5.5 12 3l2 2.5"/>',
    'lock': '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>',
    'moneyup': '<path d="M12 19V6M6 12l6-6 6 6"/>',
    'image': '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><circle cx="9" cy="10" r="1.8"/><path d="M20.5 16l-5-5-8 8.5"/>',
    'clip': '<path d="M20 11.5 12.3 19.2a4.8 4.8 0 0 1-6.8-6.8l7.7-7.7a3.2 3.2 0 0 1 4.5 4.5l-7.6 7.7a1.6 1.6 0 0 1-2.3-2.3l7-7"/>',
    'mic': '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
    'video': '<rect x="3" y="6.5" width="12.5" height="11" rx="2.5"/><path d="M15.5 10.5 21 7.5v9l-5.5-3"/>',
    'circlecam': '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3.2"/>',
    'call': '<path d="M6.5 3.5h3l1.5 4-2 1.5a12 12 0 0 0 6 6l1.5-2 4 1.5v3a2 2 0 0 1-2.2 2A16.5 16.5 0 0 1 4.5 5.7 2 2 0 0 1 6.5 3.5z"/>',
    'hangup': '<path d="M3.5 14.5c4.8-4.6 12.2-4.6 17 0l-2.2 2.4-3.3-1.4v-2.2a9 9 0 0 0-6 0v2.2l-3.3 1.4z"/>',
    'micoff': '<path d="M9 5a3 3 0 0 1 6 0v5M15 13.3A3 3 0 0 1 9 11V9M5.5 11a6.5 6.5 0 0 0 10.6 5M18.5 11a6.4 6.4 0 0 1-.6 2.7M12 17.5V21M3.5 3.5l17 17"/>',
    'camoff': '<path d="M3.5 3.5l17 17M15.5 10.5 21 7.5v9M10 6.5h3a2.5 2.5 0 0 1 2.5 2.5v3M15.5 15v.5A2.5 2.5 0 0 1 13 18H5.5A2.5 2.5 0 0 1 3 15.5v-6.5A2.5 2.5 0 0 1 5 6.6"/>',
    'trash': '<path d="M4 7h16M9.5 7V4.5h5V7M6 7l1 13h10l1-13"/>',
    'play': '<path d="M8 5.5v13l11-6.5z"/>',
    'stop': '<rect x="6.5" y="6.5" width="11" height="11" rx="2"/>',
}


@register.simple_tag
def ico(name: str, css: str = '') -> str:
    """Инлайн-иконка интерфейса из набора UI_ICONS."""
    body = UI_ICONS.get(name, UI_ICONS['info'])
    cls = f' class="{css}"' if css else ''
    return mark_safe(
        f'<svg{cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>')


@cache
def banner_file(slug):
    """Баннер слайда: banner/<slug>.webp|jpg|png, если загружен."""
    for ext in ('webp', 'jpg', 'png'):
        if (BANNERS_DIR / (slug + '.' + ext)).exists():
            return 'img/banner/' + slug + '.' + ext
        collected = Path(settings.STATIC_ROOT or '') / 'img' / 'banner' / (slug + '.' + ext)
        if collected.exists():
            return 'img/banner/' + slug + '.' + ext
    return None


@register.simple_tag
def banner_url(slug):
    """URL картинки слайда (banner/<slug>.*) или '' — для <picture>/<img>."""
    rel = banner_file(slug)
    return static_url(rel) if rel else ''


@register.simple_tag
def banner_bg(slug):
    """style с фото-фоном для слайда, если картинка загружена."""
    rel = banner_file(slug)
    if rel:
        return 'background-image:url(' + static_url(rel) + ')'
    return ''


@register.filter
def ru_plural(value, forms: str) -> str:
    """Русское склонение: {{ n|ru_plural:"отзыв,отзыва,отзывов" }} → «5 отзывов» (только слово)."""
    try:
        n = abs(int(value))
    except (TypeError, ValueError):
        n = 0
    one, few, many = (forms.split(',') + ['', '', ''])[:3]
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many
