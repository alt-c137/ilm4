"""Капча Cloudflare Turnstile — без «найдите светофоры», бесплатно, работает внутри Telegram.

Ключи: dash.cloudflare.com → Turnstile → Add site (домен ilm4.com) →
TURNSTILE_SITE_KEY и TURNSTILE_SECRET_KEY в .env. Без ключей капча выключена.
Где стоит: регистрация, «забыли пароль», вход после 3 неудачных попыток.
"""
import requests
from django.conf import settings

VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'


def enabled() -> bool:
    return bool(getattr(settings, 'TURNSTILE_SITE_KEY', '') and getattr(settings, 'TURNSTILE_SECRET_KEY', ''))


def verify(request) -> bool:
    """Проверить ответ капчи из формы. Капча выключена — всегда True."""
    if not enabled():
        return True
    token = request.POST.get('cf-turnstile-response', '')
    if not token:
        return False
    try:
        r = requests.post(VERIFY_URL, timeout=8, data={
            'secret': settings.TURNSTILE_SECRET_KEY, 'response': token,
            'remoteip': request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '')})
        return bool(r.json().get('success'))
    except (requests.RequestException, ValueError):
        return False     # Cloudflare недоступен — лучше попросить повторить, чем пустить бота
