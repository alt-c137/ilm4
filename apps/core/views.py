from django.shortcuts import render

from .blocks import get_blocks
from .catalog import build_catalog
from .models import Banner, ModuleConfig, Rate

# на главной — первые работающие разделы (порядок из админки) + плитка «Все сервисы»
POPULAR_COUNT = 11


def home(request):
    """Главная: блоки реестра по порядку + витрина разделов (§3.2)."""
    from django.conf import settings
    from django.shortcuts import redirect
    if settings.SITE_MODE == 'nikah':
        return redirect('nikah:home')
    if (request.user.is_authenticated and not (request.user.ui or {}).get('welcomed') and 'home' not in request.GET
            and getattr(settings, 'WELCOME_SCREEN', True)):
        return redirect('core:welcome')               # первый вход: выбрать знакомый вид и набор (один раз, можно пропустить)
    if request.user.is_authenticated and 'home' not in request.GET:
        # свой стартовый экран (Настройки → «С чего начинать»): платформа целиком — или сразу чаты, лента, сообщества
        from . import tabs
        go = tabs.start_url(request.user, set(ModuleConfig.objects.filter(status=ModuleConfig.ON).values_list('key', flat=True)))
        if go:
            return redirect(go)
    from . import ads, showcase
    mode = showcase.home_view(request)        # 'showcase' — витрина сервисов (по умолчанию), 'brief' — сводка «что вас ждёт»
    rates = Rate.objects.all()
    db_banners = list(Banner.objects.filter(is_active=True).order_by('order', 'id'))
    modules = list(ModuleConfig.objects.filter(in_grid=True).exclude(status=ModuleConfig.OFF))
    # разделы по смыслу — только работающие; «Общение» первым: с него начинают чаще всего
    groups = [g for g in build_catalog([m for m in ModuleConfig.objects.filter(status=ModuleConfig.ON) if m.key != 'wallet'])
              if g.key != 'more' and g.items]
    groups.sort(key=lambda g: g.key != 'talk')
    for g in groups:
        g.items = [m for m in g.items if not getattr(m, 'external', False)][:6]
    brief = None
    if request.user.is_authenticated and mode == 'brief':
        from apps.assistant.services import briefing
        brief = briefing(request.user, week=False)
        brief['on'] = set(ModuleConfig.objects.filter(status=ModuleConfig.ON).values_list('key', flat=True))
    blocks = get_blocks()
    if mode == 'showcase':                     # в витрине свежие объявления, места, вопросы и новости уже живут в плитках
        blocks = [b for b in blocks if b.key in ('banner', 'basics', 'support')]
    response = render(request, 'core/home.html', {
        'home_mode': mode, 'showcase': showcase.widgets(request.user) if mode == 'showcase' else None, 'blocks': blocks,
        'ad': ads.pick('home') if mode == 'showcase' else None,
        'home_groups': groups, 'brief': brief,
        'db_banners': db_banners,
        'rates': rates,
        'rates_updated': rates.first().updated if rates else None,
        'modules': modules,
        'popular': [m for m in modules if m.status == ModuleConfig.ON][:POPULAR_COUNT],
        'services_total': len(modules),
        'services_soon': sum(m.status == ModuleConfig.SOON for m in modules),
    })
    if request.GET.get('view') in ('showcase', 'brief') and not request.user.is_authenticated:
        response.set_cookie('ilm4_home', mode, max_age=365 * 86400, samesite='Lax')      # гость: выбор вида — в куке
    return response


def ad_go(request, pk):
    """Переход по рекламному объявлению: считаем переход и ведём по настоящей ссылке."""
    from django.http import Http404
    from django.shortcuts import redirect

    from . import ads
    url = ads.click(pk)
    if not url:
        raise Http404
    return redirect(url)


def welcome(request):
    """Первый вход: «какой вид вам привычнее» и «чем будете пользоваться». Показывается один раз; то же — в настройках."""
    from django.shortcuts import redirect

    from . import desks
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    if request.method == 'POST':                      # «Пропустить» — оставить как есть и больше не спрашивать
        desks.apply(request.user)
        return redirect('/')
    modules_on = set(ModuleConfig.objects.filter(status=ModuleConfig.ON).values_list('key', flat=True))
    return render(request, 'core/welcome.html', {'look': desks.choices(request.user, modules_on)})


def home_widgets(request):
    """Настройка витрины: переставить плитку выше / ниже, убрать или вернуть."""
    from django.shortcuts import redirect

    from . import showcase
    key = request.POST.get('key', '')
    if request.method == 'POST' and request.user.is_authenticated:
        showcase.arrange(request.user, key, request.POST.get('action', ''))
    return redirect(f'/?home=1#w-{key}' if key else '/?home=1')


def catalog(request):
    """«Все сервисы»: каталог разделов по группам с поиском."""
    modules = list(ModuleConfig.objects.exclude(status=ModuleConfig.OFF))
    groups = build_catalog(modules)
    return render(request, 'core/catalog.html', {
        'groups': groups,
        'services_total': len(modules),
        'services_on': sum(m.status == ModuleConfig.ON for m in modules),
        'services_soon': sum(m.status == ModuleConfig.SOON for m in modules),
    })


def search(request):
    """Общий поиск: одна строка ищет сервисы, людей, каналы и группы, сообщества, объявления, вакансии и новости."""
    from django.db.models import Q

    from .textsearch import icontains
    q = (request.GET.get('q') or '').strip()[:60]
    on = set(ModuleConfig.objects.filter(status=ModuleConfig.ON).values_list('key', flat=True))
    out = {'q': q, 'services': [], 'people': [], 'rooms': [], 'spaces': [], 'listings': [], 'jobs': [], 'news': [], 'any': False}
    if len(q) >= 2:
        low = q.casefold()
        for g in build_catalog(list(ModuleConfig.objects.filter(status=ModuleConfig.ON))):
            out['services'] += [m for m in g.items if low in str(m.name).casefold() or low in str(getattr(m, 'descr', '')).casefold()]
        if 'chat' in on:
            from apps.accounts import people
            from apps.chat import rooms, spaces
            if request.user.is_authenticated:
                try:
                    out['people'] = people.search(request.user, q, limit=8)
                except people.PeopleError:
                    pass
            out['rooms'] = list(rooms.catalog(q.lstrip('@'))[:8])
            if spaces.enabled():
                out['spaces'] = list(spaces.catalog(q.lstrip('@'))[:6])
        if 'buy' in on:
            from apps.core.moderation import Moderation
            from apps.market.models import Listing
            out['listings'] = list(Listing.objects.filter(status=Moderation.APPROVED, is_active=True)
                                   .filter(icontains('title', q) | icontains('description', q)).select_related('category')[:8])
        if 'jobs' in on:
            from apps.core.moderation import Moderation
            from apps.jobs.models import Vacancy
            out['jobs'] = list(Vacancy.objects.filter(status=Moderation.APPROVED).filter(icontains('title', q) | Q(city__icontains=q))[:6])
        if 'news' in on:
            from apps.news.models import NewsPost
            out['news'] = list(NewsPost.objects.filter(icontains('title', q))[:6])
        out['any'] = any(out[k] for k in ('services', 'people', 'rooms', 'spaces', 'listings', 'jobs', 'news'))
    return render(request, 'core/search.html', out)


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

    from . import tabs
    from .models import ModuleConfig, Theme
    modules_on = set(ModuleConfig.objects.filter(status=ModuleConfig.ON).values_list('key', flat=True))
    if request.method == 'POST' and request.POST.get('what') == 'look' and request.user.is_authenticated:
        from . import desks
        desks.apply(request.user, request.POST.get('design', ''), request.POST.get('desk', ''))
        back = request.POST.get('next', '')
        return redirect(back if back in ('/', '/settings/') else '/settings/?s=look')
    if request.method == 'POST' and request.POST.get('what') == 'tabs' and request.user.is_authenticated:
        # нижние кнопки сайта (сколько угодно, свой порядок) и стартовый экран
        picked = tabs.clean_ui({'tabs_site': [k for k in request.POST.getlist('tab') if k], 'start': request.POST.get('start', '')})
        user = request.user
        ui = dict(user.ui or {})
        ui.pop('start', None)
        if request.POST.get('reset') or 'tabs_site' not in picked:
            ui.pop('tabs_site', None)
        if not request.POST.get('reset'):
            ui.update(picked)
        from . import desks
        if request.POST.get('reset'):
            ui.pop('desk', None)
        else:
            desks.touched(ui)                                 # подправил кнопки — стол теперь «свой»
        user.ui = ui
        user.save(update_fields=['ui'])
        return redirect('/settings/?s=tabs')
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
    from . import desks
    mine = ((request.user.ui or {}).get('tabs_site') if request.user.is_authenticated else None) or desks.preset(request.user)['tabs_site']
    choices = tabs.choices(modules_on)
    label = {c['key']: c['label'] for c in choices}
    mine = [k for k in mine if k in label]
    section = request.GET.get('s', '')
    return render(request, 'core/settings.html', {
        's': section if section in ('chats', 'tabs', 'language', 'currency', 'look') else '', 'chat_on': 'chat' in modules_on, 'feed_on': 'feed' in modules_on,
        'look': desks.choices(request.user, modules_on),
        'all_themes': Theme.objects.all(),
        'tab_mine': [{'key': k, 'label': label[k]} for k in mine],
        'tab_rest': [c for c in choices if c['key'] not in mine],
        'start': (request.user.ui or {}).get('start', '') if request.user.is_authenticated else '',
        'start_choices': [c for c in choices if c['key'] in tabs.START]})


def set_currency(request):
    """Своя валюта для цен: кука + профиль (если вошёл). «auto» — снова определять по стране."""
    from django.http import JsonResponse
    from django.shortcuts import redirect
    from django.utils.http import url_has_allowed_host_and_scheme

    from . import money
    code = request.POST.get('currency', '')
    nxt = request.POST.get('next', '') or request.headers.get('Referer', '') or '/'
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = '/'
    wants_json = 'application/json' in request.headers.get('Accept', '')
    response = JsonResponse({'ok': True, 'currency': code}) if wants_json else redirect(nxt)
    if request.method == 'POST' and (code in money.SIGN or code == 'auto'):
        value = '' if code == 'auto' else code
        if value:
            response.set_cookie(money.COOKIE, value, max_age=365 * 86400, samesite='Lax')
        else:
            response.delete_cookie(money.COOKIE)
        if request.user.is_authenticated and request.user.currency != value:
            request.user.currency = value
            request.user.save(update_fields=['currency'])
    return response


def set_language(request):
    """Сменить язык: кука + профиль (если вошёл). POST, возвращает туда же."""
    from django.conf import settings
    from django.shortcuts import redirect
    from django.utils import translation
    from django.utils.http import url_has_allowed_host_and_scheme

    code = request.POST.get('language', '')
    nxt = request.POST.get('next', '') or '/'
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = '/'
    response = redirect(nxt)
    if request.method == 'POST' and code in dict(settings.LANGUAGES):
        translation.activate(code)
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, code, max_age=settings.LANGUAGE_COOKIE_AGE, samesite='Lax')
        if request.user.is_authenticated and request.user.language != code:
            request.user.language = code
            request.user.save(update_fields=['language'])
    return response
