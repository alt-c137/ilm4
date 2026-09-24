"""Здоровье: каталог врачей по городам, публикация врачом себя."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.decorators import module_required, pledge_required
from apps.core.models import Moderation, SiteSettings
from apps.wallet import services as wallet_services
from apps.wallet.models import Transaction

from .forms import DoctorForm
from .models import Doctor


@module_required('health')
def index(request):
    doctors = Doctor.objects.filter(status=Moderation.APPROVED)
    city = request.GET.get('city', '').strip()
    spec = request.GET.get('spec', '').strip()
    if city:
        doctors = doctors.filter(city__icontains=city)
    if spec:
        doctors = doctors.filter(category=spec)
    return render(request, 'health/index.html', {
        'doctors': doctors.select_related('owner')[:200],
        'specializations': Doctor.SPECIALIZATIONS,
        'city': city, 'spec': spec,
    })


@module_required('health')
def detail(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk, status=Moderation.APPROVED)
    return render(request, 'health/detail.html', {'doctor': doctor})


@login_required
@module_required('health')
@pledge_required
def add_doctor(request):
    """Публикация врача: если цена задана админом — платим с баланса."""
    price = SiteSettings.get_solo().doctor_publish_price
    form = DoctorForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        doctor = form.save(commit=False)
        doctor.owner = request.user
        if price:
            try:
                wallet_services.debit(request.user, price, Transaction.PURCHASE,
                                       ref='health:doctor', note='Публикация врача')
            except wallet_services.InsufficientFunds:
                messages.error(request, _('Недостаточно средств для платной публикации.'))
                return render(request, 'health/add.html', {'form': form, 'price': price})
        doctor.save()
        messages.success(request, _('Анкета отправлена — после модерации появится в каталоге.'))
        return redirect('health:index')
    return render(request, 'health/add.html', {'form': form, 'price': price})
