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


def bot_start(chat_id, nonce: str, tg_id=None) -> None:
    """/start login_<nonce>: одна кнопка «Войти и отправить мой номер» — вход и подтверждение номера сразу."""
    from apps.accounts.phone_verify import login_keyboard
    from apps.tgbot.dispatch import reply
    if not valid_nonce(nonce):
        reply(chat_id, _('Ссылка для входа устарела. Нажмите «Войти через Telegram» ещё раз.'))
        return
    cache.set(f'tglogin:tg:{tg_id or chat_id}', nonce, TTL)
    cache.delete(f'phonev:tg:{tg_id or chat_id}')        # ждём вход, а не отдельное подтверждение номера
    reply(chat_id, _('Войти в ilm4? Нажмите кнопку «📱 Войти и отправить мой номер» внизу.\n\n'
                     'Номер никто не увидит — он нужен, чтобы один человек не заводил много аккаунтов.\n'
                     'Если вы сейчас не входили в ilm4 — ничего не нажимайте: кто-то пытается войти в ваш аккаунт.'),
          login_keyboard())


def contact_login(msg: dict) -> bool:
    """Пришёл свой номер после /start login_…: войти (создать аккаунт) и подтвердить номер.
    False — входа не ждали, контакт обработает обычное подтверждение номера."""
    from apps.accounts import phone_verify
    from apps.accounts.bans import banned_text, phone_banned, tg_banned
    from apps.accounts.phones import phone_key
    from apps.accounts.telegram import _user_for
    from apps.tgbot.dispatch import reply
    tg = msg['from']
    nonce = cache.get(f'tglogin:tg:{tg["id"]}')
    if not nonce or not valid_nonce(nonce):
        return False
    done = {'remove_keyboard': True}
    cache.delete(f'tglogin:tg:{tg["id"]}')
    phone = (msg.get('contact') or {}).get('phone_number', '')
    if tg_banned(tg['id']) or phone_banned(phone_key(phone)):
        reply(msg['chat']['id'], banned_text(), done)
        return True
    user = _user_for(tg)
    if not user.is_active:
        reply(msg['chat']['id'], _('Аккаунт заблокирован'), done)
        return True
    if not user.phone_verified:
        try:
            phone_verify.confirm(user, phone, tg)
        except ValueError:
            pass     # номер уже подтверждён в другом аккаунте — вход выполняем, номер этому аккаунту не даём
    cache.set(_key(nonce), {'uid': user.pk}, TTL)
    reply(msg['chat']['id'], _('✅ Готово! Вернитесь на сайт или в приложение — вход выполнится сам.'), done)
    return True


def bot_confirm(cq: dict) -> str:
    """Кнопка «Да, это я»: привязать код к аккаунту Telegram-пользователя."""
    from apps.accounts.telegram import _user_for
    nonce = (cq.get('data') or '')[3:]
    state = cache.get(_key(nonce))
    if state is None:
        return _('Ссылка устарела — начните вход заново.')
    if state.get('uid'):
        return _('Уже подтверждено.')
    from apps.accounts.bans import banned_text, tg_banned
    if tg_banned(cq['from']['id']):
        return banned_text()
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
