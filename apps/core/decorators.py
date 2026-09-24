"""Доступ к разделу по статусу ModuleConfig (ARCHITECTURE.md §3.1)."""
from functools import wraps

from django.http import Http404
from django.shortcuts import render

from .models import ModuleConfig


def module_required(key: str):
    """Декоратор view раздела: on → view, soon → страница «Скоро», off/нет → 404."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            from django.conf import settings
            if settings.SITE_MODE == 'nikah' and key not in settings.NIKAH_MODE_KEYS:
                raise Http404   # отдельная установка никяха: чужие разделы закрыты
            module = ModuleConfig.objects.filter(key=key).first()
            if module is None or module.status == ModuleConfig.OFF:
                raise Http404
            if module.status == ModuleConfig.SOON:
                return render(request, 'core/coming_soon.html', {'module': module})
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


PUBLISH_PER_DAY = 15   # публикаций (попыток) в сутки на человека — против спама


def pledge_required(view):
    """Публикация (объявление, услуга, вакансия, перевозка, анкета, врач, место):
    автор обязан принять «Договор перед Аллахом» (includes/pledge.html).

    Галочка обязательна в форме (required), здесь — проверка на сервере на случай
    обхода. Принятие фиксируется в журнале действий.
    """
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method == 'POST':
            from django.core.cache import cache
            key = f'publish:{request.user.pk}'
            if cache.get(key, 0) >= PUBLISH_PER_DAY and not request.user.is_staff:
                from django.contrib import messages
                from django.shortcuts import redirect
                messages.error(request, 'На сегодня лимит публикаций исчерпан — защита от спама. Завтра можно снова.')
                return redirect(request.path)
            cache.set(key, cache.get(key, 0) + 1, 86400)
            if request.POST.get('pledge') != '1':
                from django.contrib import messages
                from django.shortcuts import redirect
                messages.error(request, 'Чтобы опубликовать, примите договор автора внизу формы.')
                return redirect(request.path)
            from apps.accounts.audit import log_action
            log_action(request, 'Принят договор автора', request.path)
        return view(request, *args, **kwargs)
    return wrapped
