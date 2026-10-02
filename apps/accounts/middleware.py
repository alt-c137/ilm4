"""2FA обязательна для всех админов (PASSPORT §3).

Без подтверждённого OTP-кода staff-пользователь не проходит дальше
страниц 2FA — включая всю админку Django.
"""
from django.shortcuts import redirect

SETUP_URL = '/accounts/2fa/'
VERIFY_URL = '/accounts/2fa/verify/'
ALLOWED_PREFIXES = ('/accounts/2fa', '/accounts/logout', '/admin/jsi18n')


class Staff2FARequired:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (user.is_authenticated and user.is_staff
                and not user.is_verified()
                and not request.path.startswith(ALLOWED_PREFIXES)):
            has_device = user.totpdevice_set.filter(confirmed=True).exists()
            return redirect(VERIFY_URL if has_device else SETUP_URL)
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
