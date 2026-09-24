"""Иконки и подписи раздела никях: {% nk_icon 'beard_full' %}, {{ profile|nk:'marital' }}."""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Линейные иконки 24×24 в стиле сайта (stroke = currentColor)
ICONS = {
    # кто вы
    'brother': '<path d="M8.3 7.4a3.7 3.7 0 0 1 7.4 0z"/><path d="M8.3 7.4v2.2c0 3.2 1.7 5.4 3.7 5.4s3.7-2.2 3.7-5.4V7.4"/><path d="M8.5 10.6c.7 2.5 2 3.9 3.5 3.9s2.8-1.4 3.5-3.9"/><path d="M10.6 11.2h2.8"/><path d="M5 21c.9-3 3.8-4.8 7-4.8s6.1 1.8 7 4.8"/>',
    'sister': '<path d="M12 3a5.6 5.6 0 0 0-5.6 5.6v2.9c0 4.1-1.8 6.9-2.4 9.5h16c-.6-2.6-2.4-5.4-2.4-9.5V8.6A5.6 5.6 0 0 0 12 3z"/><ellipse cx="12" cy="10" rx="2.8" ry="3.3"/>',
    # борода
    'look_m_full': '<circle cx="12" cy="7.5" r="3.4"/><path d="M8.2 8.6c0 5.2 1.6 8.4 3.8 8.4s3.8-3.2 3.8-8.4"/><path d="M9.6 12.6h4.8"/><path d="M5 21c1-2.4 3.7-3.9 7-3.9s6 1.5 7 3.9"/>',
    'look_m_short': '<circle cx="12" cy="8" r="3.6"/><path d="M8.6 9.4c.2 3 1.5 4.6 3.4 4.6s3.2-1.6 3.4-4.6"/><path d="M5 21c.9-3 3.8-5 7-5s6.1 2 7 5"/>',
    'look_m_growing': '<circle cx="12" cy="8.5" r="4"/><path d="M9.8 11.3h.01M12 12.2h.01M14.2 11.3h.01M11 13.4h.01M13 13.4h.01"/><path d="M5 21c.9-3 3.8-5 7-5s6.1 2 7 5"/>',
    'look_m_none': '<circle cx="12" cy="8.5" r="4"/><path d="M10.4 10.6c.9.7 2.3.7 3.2 0"/><path d="M5 21c.9-3 3.8-5 7-5s6.1 2 7 5"/>',
    # покрытие
    'look_f_niqab': '<path d="M12 3a5.6 5.6 0 0 0-5.6 5.6v2.9c0 4.1-1.8 6.9-2.4 9.5h16c-.6-2.6-2.4-5.4-2.4-9.5V8.6A5.6 5.6 0 0 0 12 3z"/><path d="M9 8.6h6v2H9z"/><path d="M10.5 9.6h.01M13.5 9.6h.01"/>',
    'look_f_hijab': '<path d="M12 3a5.6 5.6 0 0 0-5.6 5.6v2.9c0 4.1-1.8 6.9-2.4 9.5h16c-.6-2.6-2.4-5.4-2.4-9.5V8.6A5.6 5.6 0 0 0 12 3z"/><ellipse cx="12" cy="10" rx="2.8" ry="3.3"/>',
    'look_f_sometimes': '<path d="M12 3a6 6 0 0 0-6 6v3.6"/><path d="M12 3a6 6 0 0 1 6 6v3.6"/><circle cx="12" cy="10.2" r="3"/><path d="M5 21c.9-3 3.8-5 7-5s6.1 2 7 5"/>',
    'look_f_none': '<circle cx="12" cy="8.8" r="3.8"/><path d="M8.2 8.4c.6-2.6 2-3.9 3.8-3.9s3.2 1.3 3.8 3.9"/><path d="M5 21c.9-3 3.8-5 7-5s6.1 2 7 5"/>',
    # переезд
    'move_stay': '<path d="M4 11.5 12 5l8 6.5"/><path d="M6.5 10v9.5h11V10"/><path d="M10 19.5v-5h4v5"/>',
    'move_country': '<path d="M3.5 6.5 9 4.5l6 2 5.5-2v13l-5.5 2-6-2-5.5 2z"/><path d="M9 4.5v13M15 6.5v13"/>',
    'move_abroad': '<path d="M10.5 13.5 4 11l1.2-1.2 7 1.3 4.6-4.6a1.7 1.7 0 0 1 2.4 2.4l-4.6 4.6 1.3 7L14.7 21.7l-2.5-6.5-3 3v2.3l-1 1-1.3-3-3-1.3 1-1H7.2z"/>',
    'move_any': '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.4 2.3 3.6 5.1 3.6 8.5s-1.2 6.2-3.6 8.5c-2.4-2.3-3.6-5.1-3.6-8.5s1.2-6.2 3.6-8.5z"/>',
    # фото
    'photo_exchange': '<rect x="3" y="6" width="9" height="11" rx="2"/><rect x="12" y="4" width="9" height="11" rx="2"/><path d="M16.5 12.2s-2.2-1.3-2.2-2.8a1.1 1.1 0 0 1 2.2-.4 1.1 1.1 0 0 1 2.2.4c0 1.5-2.2 2.8-2.2 2.8z"/>',
    'photo_none': '<path d="M5 5.5h14a1.5 1.5 0 0 1 1.5 1.5v8.5A1.5 1.5 0 0 1 19 17h-8l-4.5 3.5V17H5a1.5 1.5 0 0 1-1.5-1.5V7A1.5 1.5 0 0 1 5 5.5z"/><path d="M8 10h8M8 13h5"/>',
    # принципы раздела
    'moon': '<path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z"/>',
    'eye_off': '<path d="M3.5 3.5l17 17M10.6 5.2A9.6 9.6 0 0 1 12 5c5 0 8.5 4.8 9.3 7-.4 1-1.3 2.5-2.7 3.9M6.3 6.8C4.5 8.1 3.3 10.1 2.7 12c.8 2.2 4.3 7 9.3 7 1.5 0 2.9-.4 4.1-1.1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    'gauge': '<path d="M4.5 17a8 8 0 1 1 15 0"/><path d="M12 13l3.5-4"/><circle cx="12" cy="13.5" r="1.3"/>',
    'heart': '<path d="M12 20s-7.5-4.4-7.5-10A4.3 4.3 0 0 1 12 7.6 4.3 4.3 0 0 1 19.5 10c0 5.6-7.5 10-7.5 10z"/>',
    'shield': '<path d="M12 3.5 5 6v5.5c0 4.4 3 7.9 7 9 4-1.1 7-4.6 7-9V6z"/><path d="M9 12l2 2 4-4"/>',
    'lock': '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>',
    'clock': '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    'id': '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M6 15.5c.6-1.3 1.7-2 3-2s2.4.7 3 2M14 10h4M14 13h3"/>',
    'nophone': '<rect x="7" y="3" width="10" height="18" rx="2"/><path d="M4 4l16 16"/>',
    'once': '<path d="M4 12a8 8 0 1 0 2.3-5.7"/><path d="M4 4v4h4"/><path d="M12 8v4.5"/>',
    'star': '<path d="m12 3.8 2.5 5.1 5.6.8-4 3.9 1 5.6-5.1-2.7-5 2.7 1-5.6-4.1-3.9 5.6-.8z"/>',
    'chat': '<path d="M5 5.5h14a1.5 1.5 0 0 1 1.5 1.5v8.5A1.5 1.5 0 0 1 19 17h-8l-4.5 3.5V17H5a1.5 1.5 0 0 1-1.5-1.5V7A1.5 1.5 0 0 1 5 5.5z"/>',
    'feed': '<rect x="4" y="4" width="16" height="7" rx="2"/><rect x="4" y="13" width="16" height="7" rx="2"/>',
    'user': '<circle cx="12" cy="8.5" r="3.8"/><path d="M5 20.5c.9-3.3 3.8-5.5 7-5.5s6.1 2.2 7 5.5"/>',
    'check': '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    'x': '<path d="M6 6l12 12M18 6 6 18"/>',
    'edit': '<path d="M4 20h4L19.5 8.5a2.1 2.1 0 0 0-3-3L5 17v3z"/>',
    'camera': '<path d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2.3l1.4-2h5.6l1.4 2h2.3A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5z"/><circle cx="12" cy="12.8" r="3.3"/>',
    'arrow': '<path d="M9 5l7 7-7 7"/>',
    'back': '<path d="M15 5l-7 7 7 7"/>',
    'telegram': '<path d="M20.5 4.5 3.5 11.2l5.6 2 2 6.1 3.1-3.9 4.9 3.6z"/><path d="M9.1 13.2 18 7.3"/>',
}


@register.simple_tag
def nk_icon(name: str, css: str = '') -> str:
    body = ICONS.get(name, ICONS['heart'])
    cls = f' class="{css}"' if css else ''
    return mark_safe(f'<svg{cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
                     f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>')


@register.filter
def nk(profile, field: str) -> str:
    """{{ p|nk:'marital' }} → «Разведена» (подпись по полу анкеты)."""
    return profile.label(field) if profile else ''


@register.filter
def get_item(mapping, key):
    value = mapping.get(key) if hasattr(mapping, 'get') else None
    return '' if value is None else value


@register.filter
def nk_country(value):
    """Страна из базы (по-русски) → на языке интерфейса."""
    from django.utils.translation import get_language

    from apps.nikah.geo import country_name
    return country_name(value or '', (get_language() or 'ru')[:2]) if value else ''
