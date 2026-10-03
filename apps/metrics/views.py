"""Приём «пульса» с сайта (время в разделе) и страница владельца со сводкой."""
import secrets

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import services

COOKIE = 'ilm4_v'


@csrf_exempt                       # sendBeacon не умеет слать заголовок CSRF; запрос только прибавляет секунды самому отправителю
@require_POST
def beat(request):
    anon = request.COOKIES.get(COOKIE, '')
    fresh = ''
    if not request.user.is_authenticated and not anon:
        anon = fresh = secrets.token_hex(8)
    services.record(request.user, anon, request.POST.get('s', ''), request.POST.get('t'), request.POST.get('o'))
    response = HttpResponse(status=204)
    if fresh:
        response.set_cookie(COOKIE, fresh, max_age=365 * 86400, httponly=True, samesite='Lax', secure=request.is_secure())
    return response


@staff_member_required
def stats(request):
    days = 7 if request.GET.get('days') == '7' else 90 if request.GET.get('days') == '90' else 30
    from apps.core.models import ModuleConfig
    names = dict(ModuleConfig.objects.values_list('key', 'name'))
    names.update({'home': 'Главная', 'catalog': 'Все сервисы', 'profile': 'Профиль', 'settings': 'Настройки', 'search': 'Поиск',
                  'notifications': 'Уведомления', 'my': 'Мои публикации', 'other': 'Прочее'})
    data = services.summary(days)
    for row in data['sections']:
        row['name'] = names.get(row['section'], row['section'])
    return render(request, 'metrics/stats.html', {**data, 'kind_names': {'post': 'Записи', 'msg': 'Посты каналов', 'buy': 'Объявления',
                                                                       'news': 'Новости', 'jobs': 'Работа', 'place': 'Места', 'trip': 'Попутчики',
                                                                       'topic': 'Форум', 'short': 'Короткие видео'}})
