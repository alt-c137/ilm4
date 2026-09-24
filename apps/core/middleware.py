"""Язык интерфейса из профиля: выбрал английский на телефоне — на компьютере тоже английский."""
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
