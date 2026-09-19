from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.core.decorators import module_required
from apps.core.models import Moderation

from .forms import RideForm
from .models import Ride


@module_required('transport')
def ride_list(request):
    rides = Ride.objects.filter(status=Moderation.APPROVED)
    f_from = request.GET.get('from', '').strip()
    f_to = request.GET.get('to', '').strip()
    f_type = request.GET.get('type', '').strip()
    if f_from:
        rides = rides.filter(from_city__icontains=f_from)
    if f_to:
        rides = rides.filter(to_city__icontains=f_to)
    if f_type in dict(Ride.TYPES):
        rides = rides.filter(type=f_type)
    return render(request, 'transport/list.html', {
        'rides': rides.select_related('owner')[:60],
        'types': Ride.TYPES, 'f_type': f_type,
        'f_from': f_from, 'f_to': f_to,
    })


@login_required
@module_required('transport')
def ride_create(request):
    form = RideForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ride = form.save(commit=False)
        ride.owner = request.user
        ride.save()
        messages.success(request, 'Отправлено — после модерации появится в списке.')
        return redirect('transport:list')
    return render(request, 'transport/create.html', {'form': form, 'types': Ride.TYPES})
