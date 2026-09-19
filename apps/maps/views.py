"""Карта халяль-мест: Leaflet + OSM, фильтры, добавление места (на модерацию)."""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.core.decorators import module_required
from apps.core.models import Moderation

from .forms import HalalPlaceForm
from .models import HalalPlace


def _approved(qs, request):
    """Одобренные места с учётом фильтров: город, категория, поиск, «рядом»."""
    qs = qs.filter(status=Moderation.APPROVED)
    city = request.GET.get('city', '').strip()
    category = request.GET.get('category', '').strip()
    q = request.GET.get('q', '').strip()
    if city:
        qs = qs.filter(city__icontains=city)
    if category:
        qs = qs.filter(category=category)
    if q:
        qs = qs.filter(name__icontains=q)

    lat, lon = request.GET.get('lat'), request.GET.get('lon')
    places = list(qs[:500])
    if lat and lon:
        from .services import nearby

        places = nearby(qs, lat, lon, radius_km=50)
    return places


@module_required('map')
def map_view(request):
    places = _approved(HalalPlace.objects.all(), request)
    markers = [
        {'name': p.name, 'city': p.city, 'category': p.get_category_display(),
         'address': p.address, 'phone': p.phone, 'url': p.url,
         'lat': float(p.lat), 'lon': float(p.lon),
         'distance': getattr(p, 'distance_km', None)}
        for p in places
    ]
    # '<' экранируем: иначе строка с </script> внутри JSON вырвется из <script>-блока
    markers_json = json.dumps(markers, ensure_ascii=False).replace('<', '\\u003c')
    return render(request, 'maps/map.html', {
        'places': places,
        'markers_json': markers_json,
        'categories': HalalPlace.CATEGORIES,
        'city': request.GET.get('city', ''),
        'category': request.GET.get('category', ''),
        'q': request.GET.get('q', ''),
    })


@login_required
@module_required('map')
def add_place(request):
    form = HalalPlaceForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        place = form.save(commit=False)
        place.owner = request.user
        place.save()
        messages.success(request, 'Спасибо! Место отправлено на модерацию.')
        return redirect('maps:map')
    return render(request, 'maps/add.html', {'form': form})
