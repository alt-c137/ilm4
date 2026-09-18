from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.core.decorators import module_required
from apps.core.models import Moderation

from .models import Service


@module_required('services')
def service_list(request):
    qs = Service.objects.filter(status=Moderation.APPROVED)
    kind = request.GET.get('kind', '').strip()
    if kind:
        qs = qs.filter(kind=kind)
    return render(request, 'services/list.html', {
        'services': qs[:60], 'kinds': Service.KINDS, 'kind': kind,
    })


@login_required
@module_required('services')
def service_create(request):
    if request.method == 'POST':
        errors = []
        data = {
            'name': request.POST.get('name', '').strip()[:160],
            'kind': request.POST.get('kind', 'other'),
            'city': request.POST.get('city', '').strip()[:80],
            'description': request.POST.get('description', ''),
            'price_text': request.POST.get('price_text', '').strip()[:120],
            'contact': request.POST.get('contact', '').strip()[:120],
        }
        if not data['name'] or not data['description'] or not data['contact']:
            errors.append('Название, описание и контакт обязательны.')
        if data['kind'] not in dict(Service.KINDS):
            errors.append('Выберите вид услуги из списка.')
        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            Service.objects.create(owner=request.user, **data)
            messages.success(request, 'Услуга отправлена на модерацию.')
            return redirect('services:list')
    return render(request, 'services/create.html', {'kinds': Service.KINDS})
