"""Тег виджета времён намаза для блока главной: {% prayer_widget as w %}."""
from django import template

from .. import services
from ..cities import CITIES, DEFAULT_CITY

register = template.Library()


@register.simple_tag
def prayer_widget(city_key: str = '') -> dict:
    from apps.core.models import SiteSettings

    city_key = city_key or DEFAULT_CITY
    if city_key not in CITIES:
        city_key = DEFAULT_CITY
    city_name, lat, lon, tz = CITIES[city_key]
    method = SiteSettings.get_solo().prayer_method or services.DEFAULT_METHOD
    times = services.compute(lat, lon, tz, method=method)

    now = services.local_now(tz)
    sched = services.schedule(times, now)
    until = sched['until']
    items = sched['items']

    if until['tomorrow']:
        countdown = f'завтра, в {until["time"]} — через {until["human"]}'
    else:
        countdown = f'через {until["human"]}'

    next_epoch = services.next_epoch(times, now, tz)
    return {
        'city': city_name,
        'next_epoch': next_epoch,
        'items': items,
        'next_name': until['name'],
        'next_key': until['key'],
        'next_time': until['time'],
        'current_key': sched['current_key'],
        'current_name': sched['current_name'],
        'current_time': sched['current_time'],
        'tomorrow': until['tomorrow'],
        'progress': services.prayer_progress(times, now),
        'countdown': countdown,
        'method': method,
    }


# иконки пунктов расписания (свои цвета: рассвет — фиолетовый, день — жёлтый…)
_ICONS = {
    'fajr': ('#7c5cd6', '<path d="M20.4 14.2A8.5 8.5 0 1 1 9.8 3.6a7 7 0 1 0 10.6 10.6z"/>'),
    'sunrise': ('#f59e0b', '<path d="M4 18h16M6 14a6 6 0 0 1 12 0M12 3v4M5 7l1.5 1.5M19 7l-1.5 1.5"/>'),
    'dhuhr': ('#f59e0b', '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
    'asr': ('#ea8a0c', '<circle cx="14" cy="13" r="4"/><path d="M14 5v2M22 13h-2M3 19h18"/>'),
    'maghrib': ('#ef6c2e', '<path d="M6 13a6 6 0 0 1 12 0M12 21v-6M9 18l3 3 3-3M3 19h18"/>'),
    'isha': ('#4f6cd6', '<path d="M20.4 14.2A8.5 8.5 0 1 1 9.8 3.6a7 7 0 1 0 10.6 10.6z"/>'),
}


@register.simple_tag
def prayer_icon(key: str) -> str:
    from django.utils.safestring import mark_safe
    color, body = _ICONS.get(key, _ICONS['isha'])
    return mark_safe(f'<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
                     f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>')
