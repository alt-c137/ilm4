"""Карта халяль-мест: Leaflet + OSM, фильтры, добавление места (на модерацию)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.decorators import module_required, pledge_required
from apps.core.models import Moderation
from apps.core.moderation import visible

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
         'distance': getattr(p, 'distance_km', None), 'icon': ICONS.get(p.category, 'place'), 'photo': p.photo.url if p.photo else ''}
        for p in places
    ]
    markers_json = markers                     # в шаблоне — через json_script (безопасно экранируется)
    return render(request, 'maps/map.html', {
        'places': places,
        'markers_json': markers_json,
        'categories': [(k, n, ICONS.get(k, 'place')) for k, n in HalalPlace.CATEGORIES],
        'city': request.GET.get('city', ''),
        'category': request.GET.get('category', ''),
        'q': request.GET.get('q', ''),
    })


# ключи SVG-значков категорий ({% ico %} на сайте, Ionicons/MaterialCommunityIcons в приложении) — эмодзи не используем
ICONS = {'mosque': 'mosque', 'cafe': 'cafe', 'shop': 'shop', 'hotel': 'hotel', 'butcher': 'butcher', 'other': 'place'}


@module_required('map')
def map_data(request):
    """Метки видимой области карты (JSON): ?bbox=юг,запад,север,восток&category=&q=&verified=1."""
    from django.http import JsonResponse
    try:
        s_, w, n, e = (float(x) for x in request.GET.get('bbox', '').split(','))
    except ValueError:
        return JsonResponse({'error': 'bbox'}, status=400)
    qs = HalalPlace.objects.filter(status=Moderation.APPROVED, lat__gte=s_, lat__lte=n, lon__gte=w, lon__lte=e)
    cat = request.GET.get('category', '')
    if cat:
        qs = qs.filter(category=cat)
    q = request.GET.get('q', '').strip()[:60]
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(name__icontains=q) | Q(address__icontains=q) | Q(city__icontains=q))
    rows = []
    for p in qs.prefetch_related('confirmations')[:600]:
        v = p.verification()
        if request.GET.get('verified') and v['level'] == 'none':
            continue
        rows.append({'id': p.pk, 'name': p.name, 'kind': p.category, 'icon': ICONS.get(p.category, 'place'),
                     'category': str(p.get_category_display()), 'city': p.city, 'address': p.address, 'phone': p.phone,
                     'lat': float(p.lat), 'lon': float(p.lon), 'verif': v['level'], 'verif_label': str(v['label']),
                     'brief': p.mosque_brief() if p.is_mosque else '', 'photo': p.photo.url if p.photo else ''})
    return JsonResponse({'items': rows, 'more': len(rows) >= 600})


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
                              pk=pk, **visible(request))
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
