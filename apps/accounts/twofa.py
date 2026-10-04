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


BACKUP_CODES = 10
ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'          # без похожих знаков: 0/o, 1/l/i


def _hash(code: str) -> str:
    import hashlib
    return hashlib.sha256(code.encode()).hexdigest()


def _plain(code) -> str:
    return ''.join(ch for ch in str(code or '').lower() if ch.isalnum())


def new_backup_codes(user) -> list:
    """Выдать десять новых запасных кодов (прежние перестают работать). Показываются один раз — в базе только хеши."""
    import secrets

    from .models import BackupCode
    codes = [''.join(secrets.choice(ALPHABET) for _i in range(8)) for _n in range(BACKUP_CODES)]
    BackupCode.objects.filter(user=user).delete()
    BackupCode.objects.bulk_create([BackupCode(user=user, code_hash=_hash(c)) for c in codes])
    return [f'{c[:4]}-{c[4:]}' for c in codes]


def backup_left(user) -> int:
    from .models import BackupCode
    return BackupCode.objects.filter(user=user, used_at__isnull=True).count()


def _use_backup(user, code: str):
    """Запасной код подошёл — гасим его и возвращаем устройство человека (сессия помечается «код введён»)."""
    from django.utils import timezone

    from .models import BackupCode
    taken = BackupCode.objects.filter(user=user, code_hash=_hash(code), used_at__isnull=True).update(used_at=timezone.now())
    return user.totpdevice_set.filter(confirmed=True).first() if taken else None


def check(user, code: str):
    """Проверить код: шесть цифр из приложения или запасной (восемь знаков). Возвращает устройство или None;
    после TRIES неверных попыток — пауза на 15 минут."""
    raw = _plain(code)
    code = ''.join(ch for ch in str(code or '') if ch.isdigit())[:8]
    key = f'otp:fail:{user.pk}'
    if cache.get(key, 0) >= TRIES:
        return None
    if len(raw) == 8 and not raw.isdigit():
        device = _use_backup(user, raw)
        if device is not None:
            cache.delete(key)
            return device
        code = ''
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
    user.backup_codes.all().delete()
    forget(user)


def session_locked(user, session) -> bool:
    """Сессия вошла по паролю, но код ещё не введён (для WebSocket, где нет OTP-прослойки)."""
    if not enabled(user) and not getattr(user, 'is_staff', False):
        return False
    return not (session is not None and session.get('otp_device_id'))
