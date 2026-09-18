"""Страница «Время намаза»: город или GPS-координаты, метод расчёта."""
from django.shortcuts import render

from apps.core.decorators import module_required

from . import services
from .cities import CITIES, DEFAULT_CITY


@module_required('prayer')
def index(request):
    from apps.core.models import SiteSettings

    method = request.GET.get('method') or SiteSettings.get_solo().prayer_method \
        or services.DEFAULT_METHOD
    if method not in services.METHODS:
        method = services.DEFAULT_METHOD

    # GPS: явные координаты из запроса (кнопка «Определить по GPS»)
    try:
        lat = float(request.GET.get('lat', ''))
        lon = float(request.GET.get('lon', ''))
        tz = float(request.GET.get('tz', '5'))
        place = request.GET.get('label') or 'Моё местоположение'
        city_key = None
    except ValueError:
        city_key = request.GET.get('city') or request.COOKIES.get('ilm4_city') or DEFAULT_CITY
        if city_key not in CITIES:
            city_key = DEFAULT_CITY
        place, lat, lon, tz = CITIES[city_key]

    times = services.compute(lat, lon, int(tz), method=method)
    next_key, next_name, next_left = services.next_prayer(times)
    items = [
        {'key': k, 'label': label, 'time': times[k], 'soon': k == next_key}
        for k, label in services.NAMES.items()
    ]

    response = render(request, 'prayer/index.html', {
        'items': items,
        'cities': {k: v[0] for k, v in CITIES.items()},
        'city_key': city_key, 'place': place, 'method': method,
        'methods': services.METHODS,
        'next_name': next_name, 'next_left': next_left,
    })
    if city_key:
        response.set_cookie('ilm4_city', city_key, max_age=365 * 86400)
    return response
