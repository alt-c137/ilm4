"""Тег виджета времён намаза для блока главной: {% prayer_widget as w %}."""
from django import template

from .. import services
from ..cities import CITIES, DEFAULT_CITY

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """{{ cities|get_item:city_key }} — доступ по ключу в шаблоне."""
    return (dictionary or {}).get(key)


@register.simple_tag
def prayer_widget(city_key: str = '') -> dict:
    from apps.core.models import SiteSettings

    city_key = city_key or DEFAULT_CITY
    if city_key not in CITIES:
        city_key = DEFAULT_CITY
    city_name, lat, lon, tz = CITIES[city_key]
    method = SiteSettings.get_solo().prayer_method or services.DEFAULT_METHOD
    times = services.compute(lat, lon, tz, method=method)
    next_key, next_name, next_left = services.next_prayer(times)

    items = [
        {'key': key, 'label': label, 'time': times[key], 'soon': key == next_key}
        for key, label in services.NAMES.items()
    ]
    return {
        'city': city_name,
        'items': items,
        'next_name': next_name,
        'next_left': next_left,
    }
