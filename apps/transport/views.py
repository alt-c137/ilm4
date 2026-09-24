from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from apps.core.decorators import module_required, pledge_required
from apps.core.models import Moderation

from .forms import RideForm
from .models import Ride


@module_required('transport')
def ride_list(request):
    """Маршруты и перевозчики.

    Один город — все, кто возит туда ИЛИ оттуда; оба — строго это направление.
    Популярные направления и подсказки городов — из опубликованных перевозок.
    """
    approved = Ride.objects.filter(status=Moderation.APPROVED)
    rides = approved
    f_from = request.GET.get('from', '').strip()
    f_to = request.GET.get('to', '').strip()
    f_type = request.GET.get('type', '').strip()
    if f_from and f_to:
        rides = rides.filter(from_city__icontains=f_from, to_city__icontains=f_to)
    elif f_from or f_to:
        city = f_from or f_to
        rides = rides.filter(Q(from_city__icontains=city) | Q(to_city__icontains=city))
    if f_type in dict(Ride.TYPES):
        rides = rides.filter(type=f_type)

    routes = (approved.values('from_city', 'to_city').annotate(n=Count('id'))
              .order_by('-n', 'from_city')[:12])
    cities = sorted({c for pair in approved.values_list('from_city', 'to_city') for c in pair if c})

    # группировка по направлению: «Ташкент → Москва» и его перевозчики
    groups = {}
    for r in rides.select_related('owner').order_by('from_city', 'to_city', '-created_at')[:120]:
        groups.setdefault((r.from_city, r.to_city), []).append(r)
    return render(request, 'transport/list.html', {
        'groups': [{'from': k[0], 'to': k[1], 'rides': v} for k, v in groups.items()],
        'rides_count': sum(len(v) for v in groups.values()),
        'routes': routes, 'cities': cities,
        'types': Ride.TYPES, 'f_type': f_type,
        'f_from': f_from, 'f_to': f_to,
    })


@login_required
@module_required('transport')
@pledge_required
def ride_create(request):
    form = RideForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ride = form.save(commit=False)
        ride.owner = request.user
        ride.save()
        messages.success(request, _('Отправлено — после модерации появится в списке.'))
        return redirect('transport:list')
    return render(request, 'transport/create.html', {'form': form, 'types': Ride.TYPES})
