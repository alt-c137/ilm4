from django.shortcuts import render

from .blocks import get_blocks
from .models import Banner, ModuleConfig, Rate


def home(request):
    """Главная: блоки реестра по порядку + витрина разделов (§3.2)."""
    rates = Rate.objects.all()
    db_banners = list(Banner.objects.filter(is_active=True).order_by('order', 'id'))
    return render(request, 'core/home.html', {
        'db_banners': db_banners,
        'rates': rates,
        'rates_updated': rates.first().updated if rates else None,
        'blocks': get_blocks(),
        'modules': ModuleConfig.objects.filter(in_grid=True).exclude(status=ModuleConfig.OFF),
    })


def soon(request):
    """Заглушка раздела «Скоро»: что откроется (?m=<ключ> — показать название)."""
    module = ModuleConfig.objects.filter(key=request.GET.get('m', '')).first()
    return render(request, 'core/coming_soon.html', {'module': module})
