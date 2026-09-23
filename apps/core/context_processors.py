"""Контекст для всех шаблонов: настройки, темы, меню разделов (§3.3).

Навигация: 6 главных разделов пилюлями, остальные — в выпадающее «Ещё»
(обратная связь: слишком много пилюль перегружало шапку).
"""
from django.conf import settings as django_settings

from .models import ModuleConfig, SiteSettings, Theme


def _asset_version() -> str:
    """Версия статики для ?v= в ссылках: меняется при любой правке CSS/JS — браузер
    не держит старые файлы в кэше. (В проде имена и так с хешем — не мешает.)"""
    from pathlib import Path
    root = Path(django_settings.BASE_DIR) / 'static'
    try:
        return str(int(max(f.stat().st_mtime for d in ('css', 'js') for f in (root / d).glob('*.*'))))
    except (ValueError, OSError):
        return '1'


ASSET_V = _asset_version()

# Пожертвования (Tribute). Кнопка «Поддержать» в шапке, на главной и на /support/
DONATE_URL = 'https://web.tribute.tg/d/Qrv'

def social_links():
    """Официальные каналы ilm4 из админки (Core → Соцсети и каналы)."""
    from .models import SocialLink
    return [{'key': x.kind, 'name': x.label, 'url': x.url}
            for x in SocialLink.objects.filter(is_active=True)]

# Порядок важности для верхней навигации
TOP_MENU_KEYS = ['prayer', 'buy', 'map', 'health', 'nikah', 'forum', 'chat', 'news', 'jobs', 'library']

# namespace приложения → ключ раздела (для подсветки активной пилюли)
NS_TO_KEY = {
    'prayer': 'prayer', 'market': 'buy', 'maps': 'map', 'health': 'health',
    'nikah': 'nikah', 'forum': 'forum', 'news': 'news', 'jobs': 'jobs',
    'migration': 'migration', 'services': 'services', 'library': 'library',
    'chat': 'chat', 'wallet': 'wallet', 'refugee': 'refugee', 'transport': 'transport',
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
        'menu_modules': [m for m in modules if m.key != 'wallet'],  # меню (футер, пилюли)
        'wallet_on': any(m.key == 'wallet' for m in modules),
        'escrow_on': settings_obj.escrow_enabled,
        'calls_on': (settings_obj.chat_calls_enabled or settings_obj.chat_video_calls_enabled)
        and any(m.key == 'chat' for m in modules),
        'unread_notifications': unread,
        'active_section': active_section,
        'menu_more_keys': [m.key for m in more],
        'is_home': is_home,
        'is_dark': request.COOKIES.get('ilm4_dark') == '1',
        # кнопка Google: в проде — только когда ключи заданы; в деве видна всегда
        'google_login': bool(django_settings.GOOGLE_OAUTH_CLIENT_ID and django_settings.GOOGLE_OAUTH_CLIENT_SECRET)
        or django_settings.DEBUG,
        'social_links': social_links(),
        'donate_url': DONATE_URL,
        'asset_v': ASSET_V if not django_settings.DEBUG else _asset_version(),
    }
