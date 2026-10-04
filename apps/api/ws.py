"""WebSocket для приложения: вход по заголовку `Authorization: Bearer <токен>`.

Браузер не умеет ставить этот заголовок у WebSocket — значит, чужой сайт не может
им воспользоваться, и проверка Origin (защита сессий сайта) здесь не нужна.
Без заголовка — обычный путь сайта: проверка Origin + вход по сессии.
"""
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from channels.security.websocket import AllowedHostsOriginValidator


def _bearer(scope) -> str:
    for name, value in scope.get('headers') or []:
        if name == b'authorization':
            v = value.decode('latin1')
            return v[7:].strip() if v.startswith('Bearer ') else ''
    return ''


@database_sync_to_async
def _user(raw):
    from django.contrib.auth.models import AnonymousUser

    from .models import ApiToken
    tok = ApiToken.lookup(raw)
    return tok.user if tok else AnonymousUser()


@database_sync_to_async
def _locked(user, session) -> bool:
    from apps.accounts import twofa
    return bool(getattr(user, 'is_authenticated', False)) and twofa.session_locked(user, session)


class OtpGate:
    """Сессия сайта, где введён пароль, но не введён код двухшаговой защиты, — для WebSocket как гость."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        user = scope.get('user')
        if user is not None and await _locked(user, scope.get('session')):
            from django.contrib.auth.models import AnonymousUser
            scope = {**scope, 'user': AnonymousUser()}
        return await self.inner(scope, receive, send)


class TokenOrSession:
    def __init__(self, inner):
        self.token_app = inner
        self.session_app = AllowedHostsOriginValidator(AuthMiddlewareStack(OtpGate(inner)))

    async def __call__(self, scope, receive, send):
        raw = _bearer(scope)
        if raw:
            return await self.token_app({**scope, 'user': await _user(raw)}, receive, send)
        return await self.session_app(scope, receive, send)
