from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.decorators import module_required, pledge_required
from apps.core.models import Moderation
from apps.core.moderation import visible

from .forms import VacancyForm, VacancyResponseForm
from .models import Vacancy


@module_required('jobs')
def vacancy_list(request):
    qs = Vacancy.objects.filter(status=Moderation.APPROVED)
    city = request.GET.get('city', '').strip()
    q = request.GET.get('q', '').strip()
    cat = request.GET.get('cat', '').strip()
    kind = request.GET.get('kind', Vacancy.VACANCY)
    kind = kind if kind in dict(Vacancy.KINDS) else Vacancy.VACANCY
    qs = qs.filter(kind=kind)
    if cat in dict(Vacancy.CATEGORIES):
        qs = qs.filter(category=cat)
    if city:
        qs = qs.filter(city__icontains=city)
    if q:
        qs = qs.filter(title__icontains=q)
    return render(request, 'jobs/list.html', {
        'vacancies': qs.select_related('owner')[:50],
        'categories': Vacancy.CATEGORIES, 'cat': cat,
        'city': city, 'q': q, 'kind': kind,
    })


@module_required('jobs')
def vacancy_detail(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk, **visible(request))
    return render(request, 'jobs/detail.html', {'vacancy': vacancy})


@login_required
@module_required('jobs')
@pledge_required
def vacancy_create(request):
    form = VacancyForm(request.POST or None, initial={'kind': request.GET.get('kind', Vacancy.VACANCY)})
    if request.method == 'POST' and form.is_valid():
        vacancy = form.save(commit=False)
        vacancy.owner = request.user
        vacancy.save()
        messages.success(request, _('Вакансия отправлена на модерацию.'))
        return redirect('jobs:list')
    return render(request, 'jobs/create.html', {'form': form})


@login_required
@module_required('jobs')
def vacancy_respond(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk, status=Moderation.APPROVED)
    if vacancy.owner_id == request.user.pk:
        messages.info(request, _('Это ваша вакансия.'))
        return redirect('jobs:detail', pk=pk)
    if vacancy.responses.filter(user=request.user).exists():
        messages.info(request, _('Вы уже откликнулись на эту вакансию.'))
        return redirect('jobs:detail', pk=pk)
    form = VacancyResponseForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        response_obj = form.save(commit=False)
        response_obj.vacancy = vacancy
        response_obj.user = request.user
        response_obj.save()
        messages.success(request, _('Отклик отправлен — работодатель увидит ваш email.'))
        return redirect('jobs:detail', pk=pk)
    return render(request, 'jobs/respond.html', {'form': form, 'vacancy': vacancy})
