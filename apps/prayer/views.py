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

    # GPS: явные координаты из запроса (кнопка «📍 GPS»)
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
    now = services.local_now(tz)
    until = services.until_next(times, now)
    progress = services.prayer_progress(times, now)
    next_epoch = services.next_epoch(times, now, tz)

    sched = services.schedule(times, now)
    items = sched['items']

    def city_url(key):
        return f'?city={key}&method={method}'

    response = render(request, 'prayer/index.html', {
        'items': items,
        'sched': sched,
        'progress': progress,
        'next_epoch': next_epoch,
        'until': until,
        'cities': {k: v[0] for k, v in CITIES.items()},
        'city_key': city_key, 'place': place, 'method': method,
        'methods': services.METHODS,
        'city_url': city_url,
    })
    if city_key:
        response.set_cookie('ilm4_city', city_key, max_age=365 * 86400)
    return response
