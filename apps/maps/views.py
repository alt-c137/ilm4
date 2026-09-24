"""Карта халяль-мест: Leaflet + OSM, фильтры, добавление места (на модерацию)."""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.decorators import module_required, pledge_required
from apps.core.models import Moderation

from .forms import HalalPlaceForm
from .models import HalalPlace, PlaceConfirmation


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

    qs = qs.prefetch_related('confirmations__user')
    lat, lon = request.GET.get('lat'), request.GET.get('lon')
    places = list(qs[:500])
    if lat and lon:
        from .services import nearby

        places = nearby(qs, lat, lon, radius_km=50)
    return places


@module_required('map')
def map_view(request):
    places = _approved(HalalPlace.objects.all(), request)
    for p in places:
        p.verif = p.verification()
    markers = [
        {'id': p.pk, 'name': p.name, 'city': p.city, 'category': p.get_category_display(),
         'verif': p.verif['level'], 'verif_label': p.verif['label'],
         'kind': p.category, 'brief': p.mosque_brief() if p.is_mosque else '',
         'affiliation': p.affiliation if p.is_mosque else '',
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
@pledge_required
def add_place(request):
    form = HalalPlaceForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        place = form.save(commit=False)
        place.owner = request.user
        place.save()
        messages.success(request, _('Спасибо! Место отправлено на модерацию.'))
        return redirect('maps:map')
    return render(request, 'maps/add.html', {'form': form})


@module_required('map')
def place_detail(request, pk):
    """Страница заведения: контакты, карта, отзывы и отметка «проверено»."""
    place = get_object_or_404(HalalPlace.objects.prefetch_related('confirmations__user'),
                              pk=pk, status=Moderation.APPROVED)
    mine = (PlaceConfirmation.objects.filter(place=place, user=request.user).first()
            if request.user.is_authenticated else None)
    return render(request, 'maps/detail.html', {
        'place': place,
        'confirmed': place.confirmations.filter(is_correct=True).count(),
        'verif': place.verification(),
        'branches': HalalPlace.BRANCHES, 'madhhabs': HalalPlace.MADHHABS,
        'manhajs': HalalPlace.MANHAJS, 'kinds': HalalPlace.KINDS,
        'my_confirmation': mine,
    })


@login_required
@module_required('map')
def place_confirm(request, pk):
    """«Информация верна» или «Сообщить о неточности» (с текстом — модераторам)."""
    place = get_object_or_404(HalalPlace, pk=pk, status=Moderation.APPROVED)
    if request.method != 'POST':
        return redirect('maps:detail', pk=pk)
    correct = request.POST.get('correct') == '1'
    note = request.POST.get('note', '').strip()[:500]
    # уточнение по полям мечети: только значения из списков
    choices = {'branch': HalalPlace.BRANCHES, 'madhhab': HalalPlace.MADHHABS,
               'manhaj': HalalPlace.MANHAJS, 'kind': HalalPlace.KINDS}
    suggested = {f'suggested_{f}': (v if (v := request.POST.get(f, '')) in dict(ch) else '')
                 for f, ch in choices.items()}
    if correct:
        suggested = dict.fromkeys(suggested, '')
    if not correct and not note and not any(suggested.values()):
        messages.error(request, _('Опишите, что неточно, — модератор проверит.'))
        return redirect('maps:detail', pk=pk)
    PlaceConfirmation.objects.update_or_create(
        place=place, user=request.user,
        defaults={'is_correct': correct, 'note': '' if correct else note, 'resolved': False, **suggested})
    messages.success(request, _('Спасибо, подтверждение учтено.') if correct
                     else _('Спасибо! Модератор проверит и исправит.'))
    return redirect('maps:detail', pk=pk)
