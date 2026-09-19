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

    until = services.until_next(times)
    next_key, _next_name, _left = services.next_prayer(times)
    order = list(services.PRAYER_ONLY)

    items = []
    for key, label in services.NAMES.items():
        items.append({
            'key': key, 'label': label, 'time': times[key],
            'soon': key == until['key'] and not until['tomorrow'],
            'passed': (key in order and next_key in order
                       and order.index(key) < order.index(next_key)),
        })

    if until['tomorrow']:
        countdown = f'завтра, в {until["time"]} — через {until["human"]}'
    else:
        countdown = f'через {until["human"]}'

    return {
        'city': city_name,
        'items': items,
        'next_name': until['name'],
        'countdown': countdown,
        'method': method,
    }
