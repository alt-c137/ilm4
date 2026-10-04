"""Несколько аккаунтов на одном устройстве — как в Telegram: «Добавить аккаунт», переключение без пароля (до MAX штук).

Как устроено:
* человек сам нажимает «Добавить аккаунт» — только тогда текущий аккаунт запоминается на этом устройстве;
* в браузере лежит подписанная кука ilm4_accts (HttpOnly) со списком [id, ключ]; в базе — только хеш ключа (DeviceAccount);
* переключение проверяет ключ, что аккаунт активен и что пароль с тех пор не меняли (сменил пароль — все «запомненные
  входы» этого аккаунта перестают работать);
* «Выйти» убирает аккаунт с устройства; остались другие — открывается следующий.
Сотрудникам после переключения нужно заново пройти двухшаговую проверку (сессия новая).
"""
import hashlib
import secrets

from django.contrib.auth import get_user_model
from django.core import signing
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from .models import DeviceAccount

COOKIE = 'ilm4_accts'
MAX = 5
AGE = 60 * 86400
SALT = 'ilm4.multi-account'
User = get_user_model()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def read(request) -> list:
    """[(id аккаунта, ключ)] из куки; подпись не сошлась или кука старая — пусто."""
    raw = request.COOKIES.get(COOKIE)
    if not raw:
        return []
    try:
        data = signing.loads(raw, salt=SALT, max_age=AGE)
    except signing.BadSignature:
        return []
    return [(int(u), str(t)) for u, t in data if isinstance(t, str)][:MAX]


def write(response, pairs: list, secure: bool) -> None:
    if not pairs:
        response.delete_cookie(COOKIE)
        return
    response.set_cookie(COOKIE, signing.dumps([[u, t] for u, t in pairs[:MAX]], salt=SALT), max_age=AGE, httponly=True,
                        secure=secure, samesite='Lax')


def remember(user, pairs: list) -> list:
    """Запомнить аккаунт на этом устройстве (если его ещё нет в списке). Возвращает новый список."""
    if any(u == user.pk for u, _t in pairs):
        return pairs
    if len(pairs) >= MAX:
        return pairs
    token = secrets.token_urlsafe(32)
    DeviceAccount.objects.create(user=user, token_hash=_hash(token), auth_hash=user.get_session_auth_hash())
    return [*pairs, (user.pk, token)]


def forget(user_id, pairs: list) -> list:
    for u, t in pairs:
        if u == user_id:
            DeviceAccount.objects.filter(user_id=u, token_hash=_hash(t)).delete()
    return [(u, t) for u, t in pairs if u != user_id]


def resolve(pairs: list, user_id):
    """Аккаунт для переключения — или None, если ключ не подходит, аккаунт выключен или пароль сменили."""
    for u, t in pairs:
        if u != user_id:
            continue
        row = DeviceAccount.objects.filter(user_id=u, token_hash=_hash(t)).select_related('user').first()
        if row is None or not row.user.is_active or not constant_time_compare(row.auth_hash, row.user.get_session_auth_hash()):
            return None
        DeviceAccount.objects.filter(pk=row.pk).update(used_at=timezone.now())
        return row.user
    return None


def accounts(request) -> list:
    """Аккаунты на этом устройстве для показа: [{user, current, ok}] (ok=False — нужно войти заново)."""
    pairs = read(request)
    if not pairs:
        return []
    users = {u.pk: u for u in User.objects.filter(pk__in=[u for u, _t in pairs])}
    out = []
    for uid, token in pairs:
        user = users.get(uid)
        if user is None:
            continue
        row = DeviceAccount.objects.filter(user_id=uid, token_hash=_hash(token)).first()
        ok = bool(row and user.is_active and constant_time_compare(row.auth_hash, user.get_session_auth_hash()))
        out.append({'user': user, 'current': request.user.is_authenticated and request.user.pk == uid, 'ok': ok})
    return out


def others(request) -> list:
    """Остальные аккаунты на этом устройстве — для меню (переключение одним нажатием, как в Telegram)."""
    if COOKIE not in request.COOKIES:
        return []
    return [r['user'] for r in accounts(request) if r['ok'] and not r['current']]
