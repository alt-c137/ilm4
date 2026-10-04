"""Двухшаговая защита (код из приложения-аутентификатора: Google Authenticator, Aegis, 1Password…) — для любого желающего.

Админам она обязательна (как и раньше), остальным — по желанию: Настройки → «Двухшаговая защита».
Включил — после пароля (или входа через Telegram, Google, QR-код) сайт не пускает дальше, пока не введён код;
приложение при входе просит код вместе с паролем. Код проверяется здесь, попытки ограничены.
"""
from django.core.cache import cache
from django.utils.translation import gettext as _

TRIES = 8                    # неверных кодов за окно
WINDOW = 15 * 60


def _flag(user_id) -> str:
    return f'otp:on:{user_id}'


def enabled(user) -> bool:
    """Подключена ли защита. Из кеша — спрашивают на каждом запросе."""
    if user is None or not getattr(user, 'pk', None):
        return False
    on = cache.get(_flag(user.pk))
    if on is None:
        on = user.totpdevice_set.filter(confirmed=True).exists()
        cache.set(_flag(user.pk), on, 300)
    return bool(on)


def forget(user) -> None:
    cache.delete(_flag(user.pk))


def check(user, code: str):
    """Проверить код. Возвращает устройство или None; после TRIES неверных попыток — пауза на 15 минут."""
    code = ''.join(ch for ch in str(code or '') if ch.isdigit())[:8]
    key = f'otp:fail:{user.pk}'
    if cache.get(key, 0) >= TRIES:
        return None
    if code:
        for device in user.totpdevice_set.filter(confirmed=True):
            if device.verify_token(code):
                cache.delete(key)
                return device
    cache.add(key, 0, WINDOW)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, WINDOW)
    return None


def blocked(user) -> bool:
    return cache.get(f'otp:fail:{user.pk}', 0) >= TRIES


def disable(user) -> None:
    """Отключить защиту (админам нельзя — им она обязательна)."""
    if user.is_staff:
        raise ValueError(_('Сотрудникам двухшаговая защита обязательна.'))
    user.totpdevice_set.all().delete()
    forget(user)


def session_locked(user, session) -> bool:
    """Сессия вошла по паролю, но код ещё не введён (для WebSocket, где нет OTP-прослойки)."""
    if not enabled(user) and not getattr(user, 'is_staff', False):
        return False
    return not (session is not None and session.get('otp_device_id'))
