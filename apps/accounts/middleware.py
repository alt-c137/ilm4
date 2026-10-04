"""Двухшаговая защита: админам обязательна (PASSPORT §3), остальным — по желанию (apps/accounts/twofa.py).

Без подтверждённого кода человек с включённой защитой не проходит дальше страницы ввода кода:
пароль (или вход через Telegram, Google, QR) открывает только её.
"""
from django.shortcuts import redirect

SETUP_URL = '/accounts/2fa/'
VERIFY_URL = '/accounts/2fa/verify/'
ALLOWED_PREFIXES = ('/accounts/2fa', '/accounts/logout', '/admin/jsi18n', '/static/', '/healthz', '/m/', '/sw.js',
                    '/api/')          # API входит по токену, сессию сайта не использует


class Staff2FARequired:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and not user.is_verified() and not request.path.startswith(ALLOWED_PREFIXES):
            from . import twofa
            if user.is_staff:
                return redirect(VERIFY_URL if twofa.enabled(user) else SETUP_URL)
            if twofa.enabled(user):                    # обычный человек сам включил защиту — код обязателен
                return redirect(VERIFY_URL)
        return self.get_response(request)


class LastSeenMiddleware:
    """«В сети»: отмечаем вошедшего человека на каждом запросе (в базу — не чаще раза в 45 секунд)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            from .people import touch
            touch(user)
        return self.get_response(request)
