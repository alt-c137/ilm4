"""Язык интерфейса из профиля (выбрал английский на телефоне — на компьютере тоже английский) и защитный заголовок страниц."""
from django.conf import settings
from django.utils import translation

SUPPORTED = {code for code, _name in settings.LANGUAGES}


class UserLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        lang = getattr(user, 'language', '') if user is not None and user.is_authenticated else ''
        set_cookie = False
        if lang in SUPPORTED and settings.LANGUAGE_COOKIE_NAME not in request.COOKIES:
            translation.activate(lang)
            request.LANGUAGE_CODE = lang
            set_cookie = True
        response = self.get_response(request)
        if set_cookie:
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang, max_age=settings.LANGUAGE_COOKIE_AGE,
                                samesite='Lax')
        return response


class ContentPolicyMiddleware:
    """Вторая линия защиты от чужого кода на странице (XSS).

    Первая — экранирование всего, что пишут люди. Но если где-то его пропустят, злоумышленник попробует вписать
    в имя или ссылку атрибут вроде onmouseover="…". Этот заголовок запрещает браузеру исполнять код из атрибутов
    разметки вовсе — поэтому в шаблонах нет onclick="…": подтверждения и мелкие действия идут через data-атрибуты
    (static/js/app.js). Заодно: никаких плагинов (object) и подмены базового адреса ссылок (base).
    Админка Django — отдельный интерфейс со своей разметкой, её не трогаем."""

    POLICY = "script-src-attr 'none'; object-src 'none'; base-uri 'self'"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if 'Content-Security-Policy' in response.headers or not response.headers.get('Content-Type', '').startswith('text/html'):
            return response
        match = getattr(request, 'resolver_match', None)
        if match is not None and 'admin' in (match.app_names or []):
            return response
        response.headers['Content-Security-Policy'] = self.POLICY
        return response
