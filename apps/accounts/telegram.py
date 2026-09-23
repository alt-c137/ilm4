"""Telegram: вход из мини-приложения (Mini App) и уведомления от бота.

Сайт открывается внутри Telegram (кнопка меню бота → https://<домен>/nikah/).
Telegram передаёт странице initData, подписанные токеном бота. Проверяем подпись
(https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app),
находим или создаём пользователя по telegram_id и входим — без пароля и email.

Ключ: TELEGRAM_BOT_TOKEN в .env (от @BotFather). Без токена вход из Telegram
выключен, уведомления не отправляются — сайт работает как обычно.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.http import JsonResponse
from django.views.decorators.http import require_POST

MAX_AGE = 24 * 3600   # initData старше суток не принимаем


def bot_token() -> str:
    return getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or ''


def api(method: str, data: dict | None = None, files: dict | None = None, timeout: int = 10) -> dict | None:
    """Вызов Bot API. Возвращает result или None (ошибки не ломают сайт)."""
    token = bot_token()
    if not token:
        return None
    payload = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
               for k, v in (data or {}).items() if v is not None}
    try:
        r = requests.post(f'https://api.telegram.org/bot{token}/{method}', data=payload, files=files, timeout=timeout)
        body = r.json()
    except (requests.RequestException, ValueError):
        return None
    return body.get('result') if body.get('ok') else None


def webapp_url(path: str = '/nikah/') -> str:
    """https-адрес мини-приложения (Telegram открывает только https)."""
    site = getattr(settings, 'SITE_URL', '').rstrip('/')
    return site + path if site.startswith('https://') else ''


def open_button(text: str = 'Открыть никях', path: str = '/nikah/') -> dict | None:
    url = webapp_url(path)
    return {'inline_keyboard': [[{'text': text, 'web_app': {'url': url}}]]} if url else None


def verify_init_data(init_data: str, token: str | None = None, now: float | None = None) -> dict | None:
    """Проверить подпись initData. Возвращает данные пользователя Telegram или None."""
    token = token if token is not None else bot_token()
    if not token or not init_data:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop('hash', '')
    check = '\n'.join(f'{k}={v}' for k, v in sorted(pairs.items()))
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not received or not hmac.compare_digest(expected, received):
        return None
    try:
        if (now or time.time()) - int(pairs.get('auth_date', 0)) > MAX_AGE:
            return None
        user = json.loads(pairs.get('user', '{}'))
    except (ValueError, TypeError):
        return None
    return user if user.get('id') else None


def _user_for(tg: dict):
    User = get_user_model()
    user = User.objects.filter(telegram_id=tg['id']).first()
    if user is None:
        user = User(
            username=f"tg{tg['id']}",
            email=f"tg{tg['id']}@telegram.ilm4.local",   # служебный: у Telegram-входа email нет
            first_name=(tg.get('first_name') or '')[:150],
            last_name=(tg.get('last_name') or '')[:150],
            telegram_id=tg['id'],
            telegram_username=(tg.get('username') or '')[:64],
        )
        user.set_unusable_password()
        user.save()
    return user


@require_POST   # + CSRF-токен: чужой сайт не привяжет свой Telegram к вашему аккаунту
def webapp_login(request):
    tg = verify_init_data(request.POST.get('init_data', ''))
    if tg is None:
        return JsonResponse({'ok': False, 'error': 'Не удалось подтвердить вход из Telegram'}, status=403)
    if request.user.is_authenticated:
        # уже вошёл на сайте — привязываем Telegram к этому аккаунту (для уведомлений)
        user = request.user
        owner = get_user_model().objects.filter(telegram_id=tg['id']).exclude(pk=user.pk).first()
        if owner is None and user.telegram_id != tg['id']:
            user.telegram_id = tg['id']
            user.telegram_username = (tg.get('username') or '')[:64]
            user.save(update_fields=['telegram_id', 'telegram_username'])
        return JsonResponse({'ok': True, 'reload': False})
    user = _user_for(tg)
    if not user.is_active:
        return JsonResponse({'ok': False, 'error': 'Аккаунт заблокирован'}, status=403)
    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return JsonResponse({'ok': True, 'reload': True})


def send_message(user, text: str, url: str = '') -> bool:
    """Сообщение от бота человеку, который заходил через Telegram. Ошибки не ломают сайт."""
    token = bot_token()
    if not token or not getattr(user, 'telegram_id', None):
        return False
    payload = {'chat_id': user.telegram_id, 'text': text}
    site = getattr(settings, 'SITE_URL', '').rstrip('/')
    if url and site.startswith('https://'):
        payload['reply_markup'] = json.dumps({'inline_keyboard': [[
            {'text': 'Открыть', 'web_app': {'url': site + url}}]]})
    try:
        return requests.post(f'https://api.telegram.org/bot{token}/sendMessage', data=payload, timeout=5).ok
    except requests.RequestException:
        return False


def _webapp_markup(url: str, text: str = 'Открыть') -> dict:
    site = getattr(settings, 'SITE_URL', '').rstrip('/')
    if url and site.startswith('https://'):
        return {'reply_markup': json.dumps({'inline_keyboard': [[{'text': text, 'web_app': {'url': site + url}}]]})}
    return {}


def send_protected_photo(user, jpeg: bytes, caption: str, url: str = '') -> int | None:
    """Фото защищённым сообщением: Telegram запрещает пересылку и сохранение
    (protect_content), фото скрыто под «спойлером» до нажатия. Возвращает message_id."""
    token = bot_token()
    if not token or not getattr(user, 'telegram_id', None):
        return None
    data = {'chat_id': user.telegram_id, 'caption': caption, 'protect_content': 'true', 'has_spoiler': 'true',
            **_webapp_markup(url, 'Решить')}
    try:
        r = requests.post(f'https://api.telegram.org/bot{token}/sendPhoto', data=data,
                          files={'photo': ('photo.jpg', jpeg, 'image/jpeg')}, timeout=15)
        return r.json().get('result', {}).get('message_id') if r.ok else None
    except (requests.RequestException, ValueError):
        return None


def delete_message(user, message_id) -> bool:
    token = bot_token()
    if not token or not message_id or not getattr(user, 'telegram_id', None):
        return False
    try:
        return requests.post(f'https://api.telegram.org/bot{token}/deleteMessage',
                             data={'chat_id': user.telegram_id, 'message_id': message_id}, timeout=5).ok
    except requests.RequestException:
        return False
