"""Контекст для всех шаблонов: настройки, темы, меню разделов (§3.3)."""
from .models import ModuleConfig, SiteSettings, Theme


def site(request):
    settings_obj = SiteSettings.get_solo()
    themes = Theme.objects.all()
    # Активная тема: профиль → кука → дефолт из настроек
    current = None
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated and user.theme_id:
        current = user.theme
    if current is None:
        theme_id = request.COOKIES.get('ilm4_theme')
        current = themes.filter(id=theme_id).first() or settings_obj.default_theme or themes.first()
    return {
        'site_settings': settings_obj,
        'themes': themes,
        'current_theme': current,
        'menu_modules': ModuleConfig.objects.filter(status=ModuleConfig.ON),
    }
