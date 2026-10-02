from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from apps.core.decorators import module_required, pledge_required
from apps.core.models import Moderation

from . import services
from .forms import RideForm, TripForm
from .models import Ride, Trip, TripRequest


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


# ---------- попутчики ----------

@module_required('transport')
def trip_list(request):
    """Попутчики: кто куда едет и берёт людей (и кто ищет машину)."""
    from datetime import date

    from django.core.paginator import Paginator
    g = request.GET
    f_from, f_to, role = g.get('from', '').strip()[:80], g.get('to', '').strip()[:80], g.get('role', '')
    audience = g.get('who', '')
    try:
        day = date.fromisoformat(g.get('date', '')) if g.get('date') else None
    except ValueError:
        day = None
    base = services.upcoming()
    qs = services.search(base, f_from, f_to, day, role, audience).select_related('owner')
    page = Paginator(qs, 30).get_page(g.get('page'))
    page.object_list = services.with_taken(page.object_list)
    routes = (base.values('from_city', 'to_city').annotate(n=Count('id')).order_by('-n', 'from_city')[:10])
    cities = sorted({c for pair in base.values_list('from_city', 'to_city') for c in pair if c})
    return render(request, 'transport/trips.html', {
        'page': page, 'routes': routes, 'cities': cities, 'f_from': f_from, 'f_to': f_to, 'f_role': role,
        'f_date': day.isoformat() if day else '', 'f_who': audience, 'roles': Trip.ROLES, 'audiences': Trip.AUDIENCE,
    })


@login_required
@module_required('transport')
@pledge_required
def trip_create(request):
    from apps.core import money
    from apps.core.models import SiteSettings
    from apps.core.moderation import is_newbie
    form = TripForm(request.POST or None, initial={'currency': money.viewer_currency(request)})
    if request.method == 'POST' and form.is_valid():
        trip = form.save(commit=False)
        trip.owner = request.user
        # поездка может быть уже сегодня — публикуем сразу (кроме первых публикаций новичка)
        if not SiteSettings.get_solo().trips_moderation and not is_newbie(request.user):
            trip.status = Moderation.APPROVED
        trip.save()
        messages.success(request, _('Опубликовано!') if trip.status == Moderation.APPROVED
                         else _('Отправлено — после модерации появится в списке.'))
        return redirect('transport:trip', pk=trip.pk)
    return render(request, 'transport/trip_form.html', {'form': form})


@module_required('transport')
def trip_detail(request, pk):
    from django.shortcuts import get_object_or_404

    from apps.core.moderation import visible
    trip = get_object_or_404(Trip.objects.select_related('owner'), pk=pk)
    mine = request.user.is_authenticated and trip.owner_id == request.user.pk
    if not mine:                                    # чужую — только опубликованную (модератор видит любую)
        get_object_or_404(Trip, pk=pk, **visible(request, is_active=True))
    my_request = (trip.requests.filter(user=request.user).first()
                  if request.user.is_authenticated and not mine else None)
    return render(request, 'transport/trip.html', {
        'trip': trip, 'mine': mine, 'my_request': my_request,
        'requests': trip.requests.select_related('user').exclude(status=TripRequest.CANCELLED) if mine else [],
    })


@login_required
@module_required('transport')
def trip_request(request, pk):
    from django.shortcuts import get_object_or_404
    trip = get_object_or_404(Trip, pk=pk)
    if request.method == 'POST':
        try:
            services.request_seat(trip, request.user, request.POST.get('seats'))
            messages.success(request, _('Заявка отправлена — водитель ответит в чате.'))
        except services.TripError as exc:
            messages.error(request, exc.message)
    return redirect('transport:trip', pk=pk)


@login_required
@module_required('transport')
def trip_request_act(request, req_id, action):
    from django.http import Http404
    from django.shortcuts import get_object_or_404
    req = get_object_or_404(TripRequest.objects.select_related('trip', 'user'), pk=req_id)
    if request.method == 'POST':
        try:
            if action in ('accept', 'decline'):
                services.answer(req, request.user, action == 'accept')
            elif action == 'cancel':
                services.cancel(req, request.user)
            else:
                raise Http404
        except services.TripError as exc:
            messages.error(request, exc.message)
    return redirect('transport:trip', pk=req.trip_id)
