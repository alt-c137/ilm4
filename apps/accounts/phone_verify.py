"""Подтверждение номера телефона через Telegram — бесплатно, без SMS.

Так делают крупные площадки: смотреть можно всем, а подать объявление или войти
в знакомства — только с подтверждённым номером. Один номер = один аккаунт, поэтому
боты не плодят объявления, а обойти дневной лимит никяха новым аккаунтом нельзя.

1. Сайт/приложение создаёт код и открывает t.me/<бот>?start=phone_<код>.
2. Бот показывает кнопку «📱 Отправить мой номер» (request_contact).
3. Telegram присылает номер вместе с id отправителя. Берём только свой номер
   (contact.user_id == from.id) — чужой контакт переслать не получится.
4. Страница раз в 2 секунды спрашивает статус — и идёт дальше.

В мини-приложении Telegram то же делает одна кнопка (WebApp.requestContact):
номер приходит боту, аккаунт находится по telegram_id.
"""
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext as _

from .phones import digits, phone_key

TTL = 15 * 60
PREFIX = 'phone_'


def available() -> bool:
    """Подтверждать есть чем: бот подключён."""
    return bool(getattr(settings, 'TELEGRAM_BOT_TOKEN', '') and getattr(settings, 'TELEGRAM_BOT_USERNAME', ''))


# где нужен номер → галочка в «Настройках сайта»
FLAGS = {'publish': 'phone_for_publish', 'nikah': 'phone_for_nikah', 'reviews': 'phone_for_reviews',
         'money': 'phone_for_money', 'contacts': 'phone_for_contacts'}


def needed(user, where: str) -> bool:
    """Нужно ли подтвердить номер перед действием (where — ключ FLAGS)."""
    if not user.is_authenticated or user.is_staff or user.phone_verified or not available():
        return False
    from apps.core.models import SiteSettings
    return bool(getattr(SiteSettings.get_solo(), FLAGS[where]))


def redirect_to_verify(request, where: str):
    """На страницу подтверждения, потом — обратно. JSON-запросу — ответ с кодом 'phone'."""
    from urllib.parse import urlencode

    from django.http import JsonResponse
    from django.shortcuts import redirect
    from django.urls import reverse
    from django.utils.http import url_has_allowed_host_and_scheme
    if request.method == 'GET':
        back = request.get_full_path()
    else:                               # форма (POST) — вернуть на страницу, где она была
        ref = request.headers.get('Referer', '')
        back = ref if url_has_allowed_host_and_scheme(ref, allowed_hosts={request.get_host()}) else '/'
    url = f"{reverse('accounts:phone')}?{urlencode({'next': back, 'why': where})}"
    if 'application/json' in request.headers.get('Accept', '') or request.content_type == 'application/json':
        return JsonResponse({'ok': False, 'code': 'phone', 'url': url,
                             'error': _('Сначала подтвердите номер телефона.')}, status=403)
    return redirect(url)


def required(where: str):
    """Декоратор view: действие только с подтверждённым номером (если так решил админ)."""
    from functools import wraps

    def deco(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if needed(request.user, where):
                return redirect_to_verify(request, where)
            return view(request, *args, **kwargs)
        return wrapped
    return deco


def _key(nonce: str) -> str:
    return f'phonev:{nonce}'


def create(user) -> dict:
    nonce = secrets.token_urlsafe(18)
    cache.set(_key(nonce), {'uid': user.pk}, TTL)
    bot = settings.TELEGRAM_BOT_USERNAME
    return {'nonce': nonce, 'url': f'https://t.me/{bot}?start={PREFIX}{nonce}', 'expires_in': TTL}


def status(user, nonce: str = '') -> dict:
    user.refresh_from_db(fields=['phone', 'phone_verified_at'])
    if user.phone_verified:
        return {'verified': True, 'phone': mask(user.phone)}
    state = cache.get(_key(nonce)) if nonce else None
    return {'verified': False, 'error': (state or {}).get('error', '')}


def mask(phone: str) -> str:
    d = digits(phone)
    return f'+{d[:3]} ••• •• {d[-2:]}' if len(d) >= 7 else ''


def _keyboard():
    return {'keyboard': [[{'text': _('📱 Отправить мой номер'), 'request_contact': True}]],
            'resize_keyboard': True, 'one_time_keyboard': True}


def login_keyboard():
    return {'keyboard': [[{'text': _('📱 Войти и отправить мой номер'), 'request_contact': True}]],
            'resize_keyboard': True, 'one_time_keyboard': True}


def bot_start(chat_id, tg_id, nonce: str) -> None:
    """/start phone_<код>: запомнить, чей это код, и показать кнопку «Отправить номер»."""
    from apps.tgbot.dispatch import reply
    state = cache.get(_key(nonce)) if nonce and len(nonce) <= 40 else None
    if not state:
        reply(chat_id, _('Ссылка устарела. Нажмите «Подтвердить номер» на сайте или в приложении ещё раз.'))
        return
    cache.set(f'phonev:tg:{tg_id}', nonce, TTL)
    cache.delete(f'tglogin:tg:{tg_id}')
    reply(chat_id, _('Подтвердите номер для ilm4: нажмите кнопку «📱 Отправить мой номер» внизу.\n\n'
                     'Номер не показывается другим людям. Он нужен, чтобы один человек не создавал '
                     'много аккаунтов — так мы защищаемся от спама и ботов.'), _keyboard())


def bot_contact(msg: dict) -> None:
    """Пришёл контакт: проверить, что номер свой, и подтвердить его в аккаунте."""
    from apps.tgbot.dispatch import reply
    chat_id, tg = msg['chat']['id'], msg['from']
    contact = msg.get('contact') or {}
    done = {'remove_keyboard': True}
    if contact.get('user_id') != tg['id']:
        reply(chat_id, _('Нужен именно ваш номер — нажмите кнопку «📱 Отправить мой номер» внизу.'), _keyboard())
        return
    from apps.api import tglogin
    if tglogin.contact_login(msg):                  # это вход через Telegram (сайт или приложение)
        return
    User = get_user_model()
    nonce = cache.get(f'phonev:tg:{tg["id"]}')
    state = cache.get(_key(nonce)) if nonce else None
    user = User.objects.filter(pk=state['uid']).first() if state else User.objects.filter(telegram_id=tg['id']).first()
    if user is None:
        reply(chat_id, _('Не нашли, к какому аккаунту привязать номер. Нажмите «Подтвердить номер» '
                         'на сайте или в приложении и вернитесь сюда.'), done)
        return
    try:
        confirm(user, contact.get('phone_number', ''), tg)
    except ValueError as exc:
        if nonce:
            cache.set(_key(nonce), {**state, 'error': str(exc)}, TTL)
        reply(chat_id, str(exc), done)
        return
    if nonce:
        cache.delete(f'phonev:tg:{tg["id"]}')
    reply(chat_id, _('✅ Номер подтверждён. Вернитесь на сайт или в приложение — всё откроется само.'), done)


def confirm(user, phone: str, tg: dict | None = None) -> None:
    """Записать подтверждённый номер. Номер уже подтверждён в другом аккаунте — ошибка."""
    d = digits(phone)
    if len(d) < 9:
        raise ValueError(_('Не получилось прочитать номер. Попробуйте ещё раз.'))
    from . import bans
    if bans.phone_banned(phone_key(d)) or (tg and bans.tg_banned(tg['id'])):
        raise ValueError(bans.banned_text())
    User = get_user_model()
    taken = (User.objects.filter(phone_key=phone_key(d), phone_verified_at__isnull=False)
             .exclude(pk=user.pk).exists())
    if taken:
        raise ValueError(_('Этот номер уже подтверждён в другом аккаунте ilm4. Войдите в тот аккаунт '
                           '(например, через Telegram) или напишите в поддержку.'))
    user.phone = f'+{d}'
    user.phone_verified_at = timezone.now()
    fields = ['phone', 'phone_key', 'phone_verified_at']
    if tg and user.telegram_id is None and not User.objects.filter(telegram_id=tg['id']).exists():
        user.telegram_id = tg['id']              # заодно — уведомления бота этому человеку
        user.telegram_username = (tg.get('username') or '')[:64]
        fields += ['telegram_id', 'telegram_username']
    user.save(update_fields=fields)
    from .models import AuditLog
    AuditLog.objects.create(user=user, action='Номер подтверждён через Telegram', target=mask(user.phone))
