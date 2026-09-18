from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import module_required
from apps.core.models import Moderation

from .forms import VacancyForm, VacancyResponseForm
from .models import Vacancy


@module_required('jobs')
def vacancy_list(request):
    qs = Vacancy.objects.filter(status=Moderation.APPROVED)
    city = request.GET.get('city', '').strip()
    q = request.GET.get('q', '').strip()
    if city:
        qs = qs.filter(city__icontains=city)
    if q:
        qs = qs.filter(title__icontains=q)
    return render(request, 'jobs/list.html', {
        'vacancies': qs.select_related('owner')[:50],
        'city': city, 'q': q,
    })


@module_required('jobs')
def vacancy_detail(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk, status=Moderation.APPROVED)
    return render(request, 'jobs/detail.html', {'vacancy': vacancy})


@login_required
@module_required('jobs')
def vacancy_create(request):
    form = VacancyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        vacancy = form.save(commit=False)
        vacancy.owner = request.user
        vacancy.save()
        messages.success(request, 'Вакансия отправлена на модерацию.')
        return redirect('jobs:list')
    return render(request, 'jobs/create.html', {'form': form})


@login_required
@module_required('jobs')
def vacancy_respond(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk, status=Moderation.APPROVED)
    form = VacancyResponseForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        response_obj = form.save(commit=False)
        response_obj.vacancy = vacancy
        response_obj.user = request.user
        response_obj.save()
        messages.success(request, 'Отклик отправлен — работодатель увидит ваш email.')
        return redirect('jobs:detail', pk=pk)
    return render(request, 'jobs/respond.html', {'form': form, 'vacancy': vacancy})
