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
    'refresh': '<path d="M20 11a8 8 0 0 0-14.3-4.6L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.3 4.6L20 16"/><path d="M20 20v-4h-4"/>',
    'camera': '<path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.2l1.2-1.8h6.2L16.3 6h1.2A2.5 2.5 0 0 1 20 8.5v8A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5z"/><circle cx="12" cy="12.5" r="3.4"/>',
    'brush': '<path d="M18.4 3.6a2 2 0 0 1 2 2c0 1.1-6.2 8.2-8.6 10.4l-3-3C11 10.600 17.300 3.6 18.4 3.6z"/><path d="M8.800 13 6.5 13.600c-1.7.5-2.2 2.200-2.300 3.700 0 1-.5 1.900-1.200 2.500 2.500.7 6.800.3 7.900-2.300l.9-1.500"/>',
    'coins': '<circle cx="9" cy="9" r="5.5"/><path d="M14.5 9.600a5.5 5.5 0 1 1-4.900 4.900"/><path d="M9 7v4M7.500 8h1.500"/>',
    'sd': '<rect x="3.5" y="6" width="17" height="12" rx="3"/><path d="M10.200 10.200c-.4-.5-1-.7-1.600-.7-.9 0-1.600.5-1.600 1.200 0 1.700 3.400.8 3.400 2.600 0 .700-.7 1.200-1.700 1.200-.7 0-1.400-.3-1.800-.8"/><path d="M13 9.500v5h1.200a2.500 2.500 0 0 0 0-5z"/>',
    'back': '<path d="M15 5l-7 7 7 7"/>',
    'search': '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4-4"/>',
    'grid': '<rect x="4" y="4" width="6.5" height="6.5" rx="2"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="2"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="2"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="3.25"/>',
    'home': '<path d="M3.5 10.5 12 3.5l8.5 7V19a1.5 1.5 0 0 1-1.5 1.5h-4v-6h-6v6H5A1.5 1.5 0 0 1 3.5 19z"/>',
    'pin': '<path d="M12 21s-6-5.3-6-10a6 6 0 0 1 12 0c0 4.7-6 10-6 10z"/><circle cx="12" cy="11" r="2.2"/>',
    'calendar': '<rect x="3.5" y="5" width="17" height="15" rx="2.5"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/>',
    'clock': '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    'chart': '<path d="M4 20V10M10 20V4M16 20v-7M21 20H3"/>',
    'monitor': '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M8.5 20h7M12 16.500V20"/>',
    'qr': '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><path d="M14 14h2.500v2.500H14zM20 14v2M17.500 17.500H20V20M14 19.500V20h1.500"/>',
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
    'megaphone': '<path d="M4 10v4a1 1 0 0 0 1 1h2l5 4V5L7 9H5a1 1 0 0 0-1 1z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
    'users': '<circle cx="9" cy="8.5" r="3.5"/><path d="M2.5 20c.9-3.3 3.4-5 6.5-5s5.6 1.7 6.5 5"/><path d="M16 5.2a3.5 3.5 0 0 1 0 6.6M18 15.3c1.8.7 3 2.2 3.5 4.7"/>',
    'check': '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    'copy': '<rect x="8.5" y="8.5" width="11" height="11" rx="2.5"/><path d="M5.5 15.5h-1a1 1 0 0 1-1-1v-9a2 2 0 0 1 2-2h9a1 1 0 0 1 1 1v1"/>',
    'bell': '<path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
    'belloff': '<path d="M8.6 4.6A6 6 0 0 1 18 9.5c0 3.2.8 5.3 1.6 6.6M6.2 7.4C6.1 8 6 8.7 6 9.5c0 5.5-2.5 7.5-2.5 7.5H17M13.7 21a2 2 0 0 1-3.4 0M3 3l18 18"/>',
    'pause': '<path d="M8.5 5.5v13M15.5 5.5v13"/>',
    'at': '<circle cx="12" cy="12" r="3.6"/><path d="M15.6 8.6v4.6a2.4 2.4 0 0 0 4.9 0V12a8.5 8.5 0 1 0-3.4 6.8"/>',
    'link': '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    'dots': '<circle cx="12" cy="5.5" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="12" cy="18.5" r="1.3"/>',
    'file': '<path d="M13.5 3.5h-7a1.5 1.5 0 0 0-1.5 1.5v14a1.5 1.5 0 0 0 1.5 1.5h11a1.5 1.5 0 0 0 1.5-1.5v-10zM13.5 3.5v5.5H19"/>',
    'trash': '<path d="M4 7h16M9.5 7V4.5h5V7M6 7l1 13h10l1-13"/>',
    'play': '<path d="M8 5.5v13l11-6.5z"/>',
    'stop': '<rect x="6.5" y="6.5" width="11" height="11" rx="2"/>',
    # --- мессенджер «как в Telegram» ---
    'tack': '<path d="M14.5 3.5l6 6-3 1-3.2 3.2.5 4.3-1.6 1.6-4.4-4.4L4 20l4.8-4.8-4.4-4.4L6 9.2l4.3.5L13.5 6.5z"/>',
    'untack': '<path d="M14.5 3.5l6 6-3 1-3.2 3.2.5 4.3-1.6 1.6-4.4-4.4L4 20l4.8-4.8-4.4-4.4L6 9.2l4.3.5L13.5 6.5zM3.5 3.5l17 17"/>',
    'archive': '<rect x="3.5" y="4.5" width="17" height="4.5" rx="1.2"/><path d="M5 9v9.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V9M12 11.5v5M9.5 14.2l2.5 2.5 2.5-2.5"/>',
    'unarchive': '<rect x="3.5" y="4.5" width="17" height="4.5" rx="1.2"/><path d="M5 9v9.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V9M12 17v-5M9.5 14.3l2.5-2.5 2.5 2.5"/>',
    'folder': '<path d="M3.5 7A1.5 1.5 0 0 1 5 5.5h4.2l2 2.2H19a1.5 1.5 0 0 1 1.5 1.5v8.3A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5z"/>',
    'folderplus': '<path d="M3.5 7A1.5 1.5 0 0 1 5 5.5h4.2l2 2.2H19a1.5 1.5 0 0 1 1.5 1.5v8.3A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5zM12 10.8v5M9.5 13.3h5"/>',
    'reply': '<path d="M9.5 7 4.5 12l5 5M4.5 12h9a6 6 0 0 1 6 6v.5"/>',
    'forward': '<path d="M14.5 7l5 5-5 5M19.5 12h-9a6 6 0 0 0-6 6v.5"/>',
    'bookmark': '<path d="M7 4h10a1 1 0 0 1 1 1v15l-6-4.2L6 20V5a1 1 0 0 1 1-1z"/>',
    'smile': '<circle cx="12" cy="12" r="8.5"/><path d="M8.5 14.2a4.2 4.2 0 0 0 7 0"/><circle cx="9.2" cy="10" r=".6"/><circle cx="14.8" cy="10" r=".6"/>',
    'close': '<path d="M6 6l12 12M18 6 6 18"/>',
    'down': '<path d="M6 9.5l6 6 6-6"/>',
    'up': '<path d="M6 14.5l6-6 6 6"/>',
    'sliders': '<path d="M4 7h9M17 7h3M4 12h3M11 12h9M4 17h11M19 17h1"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="17" r="2"/>',
    'unread': '<path d="M20.5 11.5a8 8 0 0 1-11.4 7.2L3.5 20.5l1.8-5.5a8 8 0 0 1 9-11.2"/><circle cx="18.5" cy="5.5" r="2.6" fill="currentColor" stroke="none"/>',
    'checks': '<path d="M2.5 12.5l4 4 8-9M10.5 16.5l1.3 1.3L21.5 7.5"/>',
    'comment': '<path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H9l-4.5 2.5v-5A7.5 7.5 0 0 1 4 11.5a8 8 0 0 1 16 0z"/>',
    'poll': '<path d="M6 19V11M12 19V5M18 19v-5"/>',
    'download': '<path d="M12 4v11M7.5 11 12 15.5 16.5 11M5 19.5h14"/>',
    'broom': '<path d="M14 4l6 6M4 20c0-4 2-7 5.5-9l4 4C11.500 18.500 8 20 4 20zM12 9l3 3"/>',
    'exit': '<path d="M14 4.500H6.500A1.500 1.500 0 0 0 5 6v12a1.500 1.500 0 0 0 1.500 1.500H14M10 12h10M16.500 8.500 20 12l-3.500 3.500"/>',
    'repost': '<path d="M17 3l4 4-4 4"/><path d="M3 11V10a3 3 0 0 1 3-3h15"/><path d="M7 21l-4-4 4-4"/><path d="M21 13v1a3 3 0 0 1-3 3H3"/>',
    'more': '<circle cx="5.5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="18.5" cy="12" r="1.3"/>',
}


def icon_body(name: str) -> str | None:
    """Содержимое значка: свой набор UI_ICONS, затем Lucide (apps/core/icons_lucide.py)."""
    from apps.core.icons_lucide import LUCIDE
    return UI_ICONS.get(name) or LUCIDE.get(name)


@register.simple_tag
def ico(name: str, css: str = '') -> str:
    """Инлайн-иконка интерфейса: {% ico 'pin' %}. Эмодзи в интерфейсе не используем — только такие значки."""
    body = icon_body(name) or UI_ICONS['info']
    cls = f' class="{css}"' if css else ''
    return mark_safe(
        f'<svg{cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>')


@register.simple_tag
def hicon(value: str, css: str = '') -> str:
    """Значок привычки/папки, выбранный человеком: ключ из набора → SVG; старое значение-эмодзи показываем как есть."""
    if value and icon_body(str(value)):
        return ico(str(value), css)
    return format_html('<span class="emo">{}</span>', value or '')


@register.simple_tag
def ui_icons(*names):
    """Иконки для скриптов: <script type="application/json" id="ui-icons">{"reply": "<svg…>", …}</script>."""
    import json
    data = {n: str(ico(n)) for n in names if icon_body(n)}
    return mark_safe('<script type="application/json" id="ui-icons">'
                     + json.dumps(data, ensure_ascii=False).replace('</', '<\\/') + '</script>')


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


@register.simple_tag
def face(user, section='board'):
    """Как показать автора в разделе (с учётом его «маски»): {% face owner 'board' as seller %} → seller.name / avatar / link."""
    from apps.accounts import people
    return people.face(user, section)

