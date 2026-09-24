"""Вход и регистрация через Google (OpenID Connect, authorization code flow).

Без сторонних пакетов: редирект на Google → код → токен → профиль (email, имя).
Ключи — в .env: GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET
(Google Cloud Console → APIs & Services → Credentials → OAuth client ID → Web).
Разрешённый redirect URI: https://<домен>/accounts/google/callback/

Существующий аккаунт находится по email — вход; нет — создаётся новый.
Для сотрудников 2FA по-прежнему обязательна (Staff2FARequired).
"""
import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.utils.translation import gettext as _

from .audit import log_action

AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
USERINFO_URL = 'https://openidconnect.googleapis.com/v1/userinfo'
SESSION_KEY = 'google_oauth'


def is_configured() -> bool:
    return bool(getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
                and getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', ''))


def _redirect_uri(request) -> str:
    return request.build_absolute_uri(reverse('accounts:google_callback'))


def _safe_next(request, url: str) -> str:
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return url
    return reverse('core:home')


def google_start(request):
    """Кнопка «Войти через Google»: запоминаем state и уходим на Google."""
    if not is_configured():
        messages.info(request, _('Вход через Google скоро заработает. Пока войдите по email.'))
        return redirect('accounts:login')
    state = secrets.token_urlsafe(24)
    request.session[SESSION_KEY] = {'state': state, 'next': request.GET.get('next', '')}
    params = {
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'redirect_uri': _redirect_uri(request),
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'prompt': 'select_account',
        'access_type': 'online',
    }
    return redirect(f'{AUTH_URL}?{urlencode(params)}')


def _unique_username(base: str) -> str:
    User = get_user_model()
    base = (slugify(base) or 'user')[:24]
    name, n = base, 1
    while User.objects.filter(username__iexact=name).exists():
        n += 1
        name = f'{base}{n}'
    return name


def google_callback(request):
    """Google вернул код: меняем на токен, берём профиль, входим."""
    saved = request.session.pop(SESSION_KEY, None) or {}
    fail = _('Не удалось войти через Google. Попробуйте ещё раз или войдите по email.')
    if (not is_configured() or request.GET.get('error') or not saved
            or not secrets.compare_digest(request.GET.get('state', ''), saved.get('state', ''))):
        messages.error(request, fail)
        return redirect('accounts:login')

    try:
        token = requests.post(TOKEN_URL, data={
            'code': request.GET.get('code', ''),
            'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
            'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
            'redirect_uri': _redirect_uri(request),
            'grant_type': 'authorization_code',
        }, timeout=10).json()
        info = requests.get(USERINFO_URL, timeout=10, headers={
            'Authorization': f'Bearer {token.get("access_token", "")}'}).json()
    except (requests.RequestException, ValueError):
        messages.error(request, fail)
        return redirect('accounts:login')

    email = (info.get('email') or '').strip().lower()
    if not email or not info.get('email_verified'):
        messages.error(request, _('Google не подтвердил email этого аккаунта.'))
        return redirect('accounts:login')

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    created = False
    if user is None:
        user = User(
            username=_unique_username(email.split('@')[0]),
            email=email,
            first_name=(info.get('given_name') or '')[:150],
            last_name=(info.get('family_name') or '')[:150],
        )
        user.set_unusable_password()
        user.save()
        created = True
    if not user.is_active:
        messages.error(request, _('Аккаунт заблокирован. Напишите в поддержку.'))
        return redirect('accounts:login')

    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    log_action(request, 'Вход через Google' + (' (новый аккаунт)' if created else ''), email)
    messages.success(request, (_('Добро пожаловать, {v1}!').format(v1=user.get_display_name()) if created
                               else _('С возвращением, {v1}!').format(v1=user.get_display_name())))
    return redirect(_safe_next(request, saved.get('next', '')))
