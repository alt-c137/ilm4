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
            module = ModuleConfig.objects.filter(key=key).first()
            if module is None or module.status == ModuleConfig.OFF:
                raise Http404
            if module.status == ModuleConfig.SOON:
                return render(request, 'core/coming_soon.html', {'module': module})
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
