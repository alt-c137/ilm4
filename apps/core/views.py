from django.shortcuts import render

from .blocks import get_blocks
from .models import ModuleConfig


def home(request):
    """Главная: блоки реестра по порядку + витрина разделов (§3.2)."""
    return render(request, 'core/home.html', {
        'blocks': get_blocks(),
        'modules': ModuleConfig.objects.filter(in_grid=True).exclude(status=ModuleConfig.OFF),
    })
