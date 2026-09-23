from django.shortcuts import render

from .blocks import get_blocks
from .catalog import build_catalog
from .models import Banner, ModuleConfig, Rate, SiteSettings

# на главной — первые работающие разделы (порядок из админки) + плитка «Все сервисы»
POPULAR_COUNT = 11


def home(request):
    """Главная: блоки реестра по порядку + витрина разделов (§3.2)."""
    rates = Rate.objects.all()
    db_banners = list(Banner.objects.filter(is_active=True).order_by('order', 'id'))
    modules = list(ModuleConfig.objects.filter(in_grid=True).exclude(status=ModuleConfig.OFF))
    return render(request, 'core/home.html', {
        'db_banners': db_banners,
        'rates': rates,
        'rates_updated': rates.first().updated if rates else None,
        'blocks': get_blocks(),
        'modules': modules,
        'popular': [m for m in modules if m.status == ModuleConfig.ON][:POPULAR_COUNT],
        'services_total': len(modules),
        'services_soon': sum(m.status == ModuleConfig.SOON for m in modules),
    })


def catalog(request):
    """«Все сервисы»: каталог разделов по группам с поиском."""
    modules = list(ModuleConfig.objects.exclude(status=ModuleConfig.OFF))
    groups = build_catalog(modules)
    if not SiteSettings.get_solo().feed_enabled:   # выключенная лента — не показываем в каталоге
        for g in groups:
            g.items = [m for m in g.items if getattr(m, 'key', '') != 'feed']
        groups = [g for g in groups if g.items]
    return render(request, 'core/catalog.html', {
        'groups': groups,
        'services_total': len(modules),
        'services_on': sum(m.status == ModuleConfig.ON for m in modules),
        'services_soon': sum(m.status == ModuleConfig.SOON for m in modules),
    })


def soon(request):
    """Заглушка раздела «Скоро»: что откроется (?m=<ключ> — показать название)."""
    module = ModuleConfig.objects.filter(key=request.GET.get('m', '')).first()
    return render(request, 'core/coming_soon.html', {'module': module})


def settings_view(request):
    """Настройки оформления: тема (светлая/тёмная) и цвет акцента.

    Гость — куки; вошедший — ещё и профиль (user.theme), иначе при следующем
    заходе тема из профиля перебьёт выбор.
    """
    from django.shortcuts import redirect

    from .models import Theme

    if request.method == 'POST':
        response = redirect('core:settings')
        mode = request.POST.get('mode')
        if mode in ('light', 'dark'):
            response.set_cookie('ilm4_dark', '1' if mode == 'dark' else '0',
                                max_age=365 * 86400, samesite='Lax')
        theme = Theme.objects.filter(pk=request.POST.get('theme') or 0).first()
        if theme:
            response.set_cookie('ilm4_theme', str(theme.pk), max_age=365 * 86400, samesite='Lax')
            if request.user.is_authenticated:
                request.user.theme = theme
                request.user.save(update_fields=['theme'])
        return response
    return render(request, 'core/settings.html', {'all_themes': Theme.objects.all()})


def feed(request):
    """Лента (прототип): вертикальные карточки из реального контента платформы —
    новости, объявления, вопросы, места, вакансии. Позже сюда придут посты
    каналов/блогов и короткие видео (docs/ROADMAP.md §3)."""
    from django.http import Http404
    if not SiteSettings.get_solo().feed_enabled:
        raise Http404
    from itertools import zip_longest

    from apps.core.models import Moderation
    from apps.forum.models import Topic
    from apps.jobs.models import Vacancy
    from apps.maps.models import HalalPlace
    from apps.market.models import Listing
    from apps.news.models import NewsPost

    news = [{'kind': 'Новости', 'title': p.title, 'text': p.summary, 'img': p.cover.url if p.cover else '',
             'url': f'/news/{p.slug}/', 'meta': p.created_at} for p in NewsPost.objects.all()[:10]]
    buy = [{'kind': 'Маркет', 'title': x.title, 'text': x.description[:160], 'img': x.photo.url if x.photo else '',
            'url': f'/buy/{x.pk}/', 'meta': x.created_at, 'price': f'{x.price:,.0f} {x.get_currency_display()}'.replace(',', ' ')}
           for x in Listing.objects.filter(status=Moderation.APPROVED, is_active=True)[:10]]
    qa = [{'kind': 'Вопрос', 'title': t.title, 'text': t.body[:200], 'img': '', 'url': f'/forum/{t.pk}/',
           'meta': t.created_at, 'author': t.author.get_display_name()}
          for t in Topic.objects.filter(status=Moderation.APPROVED).select_related('author')[:10]]
    places = [{'kind': p.get_category_display(), 'title': p.name, 'text': p.description[:160] or p.city,
               'img': p.photo.url if p.photo else '', 'url': f'/map/{p.pk}/', 'meta': p.created_at}
              for p in HalalPlace.objects.filter(status=Moderation.APPROVED)[:10]]
    jobs = [{'kind': 'Вакансия', 'title': v.title, 'text': f'{v.company} · {v.city}', 'img': '',
             'url': f'/jobs/{v.pk}/', 'meta': v.created_at, 'price': v.salary}
            for v in Vacancy.objects.filter(status=Moderation.APPROVED)[:10]]
    items = [x for group in zip_longest(news, buy, qa, places, jobs) for x in group if x][:40]
    for i, it in enumerate(items):
        it['id'] = i
        it['tone'] = i % 5
    return render(request, 'core/feed.html', {'items': items})
