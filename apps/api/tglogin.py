"""Вход в приложение через Telegram-бота — без паролей и без SMS.

1. Приложение просит одноразовый код (nonce) и открывает t.me/<бот>?start=login_<nonce>.
2. Бот спрашивает: «Войти в приложение ilm4?» — человек жмёт кнопку «Да, это я».
3. Приложение раз в 2 секунды спрашивает сервер — и получает токен.

Кнопка подтверждения нужна против фишинга: без неё злоумышленник мог бы прислать
свою ссылку и войти в чужой аккаунт одним нажатием «Start». Код живёт 10 минут
и срабатывает один раз.
"""
import secrets

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext as _

TTL = 10 * 60
PREFIX = 'login_'


def _key(nonce: str) -> str:
    return f'tglogin:{nonce}'


def create() -> dict:
    nonce = secrets.token_urlsafe(24)
    cache.set(_key(nonce), {'uid': None}, TTL)
    bot = getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or ''
    return {'nonce': nonce, 'url': f'https://t.me/{bot}?start={PREFIX}{nonce}' if bot else '', 'expires_in': TTL}


def valid_nonce(nonce: str) -> bool:
    return bool(nonce) and len(nonce) <= 40 and cache.get(_key(nonce)) is not None


def bot_start(chat_id, nonce: str) -> None:
    """/start login_<nonce>: спросить подтверждение."""
    from apps.tgbot.dispatch import reply
    if not valid_nonce(nonce):
        reply(chat_id, _('Ссылка для входа устарела. Нажмите «Войти через Telegram» в приложении ещё раз.'))
        return
    reply(chat_id, _('Войти в приложение ilm4 на вашем телефоне?\n\nЕсли вы сейчас не входили в приложение — '
                     'ничего не нажимайте: кто-то пытается войти в ваш аккаунт.'),
          {'inline_keyboard': [[{'text': _('✅ Да, это я'), 'callback_data': f'lg:{nonce}'}]]})


def bot_confirm(cq: dict) -> str:
    """Кнопка «Да, это я»: привязать код к аккаунту Telegram-пользователя."""
    from apps.accounts.telegram import _user_for
    nonce = (cq.get('data') or '')[3:]
    state = cache.get(_key(nonce))
    if state is None:
        return _('Ссылка устарела — начните вход заново.')
    if state.get('uid'):
        return _('Уже подтверждено.')
    user = _user_for(cq['from'])
    if not user.is_active:
        return _('Аккаунт заблокирован')
    cache.set(_key(nonce), {'uid': user.pk}, TTL)
    return _('Готово! Вернитесь в приложение.')


def poll(nonce: str):
    """Пользователь, если вход подтверждён (код сгорает), иначе None."""
    from django.contrib.auth import get_user_model
    state = cache.get(_key(nonce))
    if not state or not state.get('uid'):
        return None
    cache.delete(_key(nonce))
    return get_user_model().objects.filter(pk=state['uid'], is_active=True).first()
