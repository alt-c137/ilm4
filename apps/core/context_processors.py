"""Контекст для всех шаблонов: настройки, темы, меню разделов (§3.3).

Навигация: 6 главных разделов пилюлями, остальные — в выпадающее «Ещё»
(обратная связь: слишком много пилюль перегружало шапку).
"""
from .models import ModuleConfig, SiteSettings, Theme

# Порядок важности для верхней навигации
TOP_MENU_KEYS = ['prayer', 'buy', 'map', 'health', 'nikah', 'forum']

# namespace приложения → ключ раздела (для подсветки активной пилюли)
NS_TO_KEY = {
    'prayer': 'prayer', 'market': 'buy', 'maps': 'map', 'health': 'health',
    'nikah': 'nikah', 'forum': 'forum', 'news': 'news', 'jobs': 'jobs',
    'migration': 'migration', 'services': 'services', 'library': 'library',
    'chat': 'chat', 'wallet': 'wallet',
}


def site(request):
    settings_obj = SiteSettings.get_solo()
    themes = Theme.objects.all()
    # Активная тема: профиль → кука → дефолт из настроек
    current = None
    user = getattr(request, 'user', None)
    unread = 0
    if user is not None and user.is_authenticated:
        if user.theme_id:
            current = user.theme
        unread = user.notifications.filter(read=False).count()
    if current is None:
        theme_id = request.COOKIES.get('ilm4_theme')
        current = (themes.filter(id=theme_id).first()
                   or settings_obj.default_theme or themes.first())

    modules = list(ModuleConfig.objects.filter(status=ModuleConfig.ON))
    by_key = {m.key: m for m in modules}
    top = [by_key.pop(k) for k in TOP_MENU_KEYS if k in by_key]
    more = sorted(by_key.values(), key=lambda m: m.order)  # остальные — «Ещё ▾»

    # активная пилюля: по namespace открытого приложения
    resolver = getattr(request, 'resolver_match', None)
    active_section = NS_TO_KEY.get(getattr(resolver, 'namespace', ''), '')
    is_home = bool(resolver and resolver.url_name == 'home')

    return {
        'site_settings': settings_obj,
        'themes': themes,
        'current_theme': current,
        'menu_top': top,
        'menu_more': more,
        'menu_modules': modules,  # полное меню (футер, витрина)
        'unread_notifications': unread,
        'active_section': active_section,
        'menu_more_keys': [m.key for m in more],
        'is_home': is_home,
    }
