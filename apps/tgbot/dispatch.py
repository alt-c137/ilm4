"""Обработка обновлений Telegram-бота — общая для вебхука (сервер) и опроса (ПК).

Бот — «дверь» в никях: /start открывает мини-приложение; видео-кружок — верификация;
кнопки в чате модераторов — одобрение анкет; платежи Telegram Stars — пополнение.
"""
import logging

from django.conf import settings
from django.core.cache import cache

from apps.accounts.telegram import api, open_button

log = logging.getLogger(__name__)

WELCOME = ('Ассаляму алейкум! Это никях ilm4 — знакомство для брака по Корану и Сунне.\n\n'
           'Анкеты без фото, совместимость по убеждениям, чат — только при взаимной симпатии. '
           'Нажмите кнопку ниже, чтобы открыть.')


def reply(chat_id, text, markup=None):
    return api('sendMessage', {'chat_id': chat_id, 'text': text, 'reply_markup': markup})


def handle_update(update: dict) -> None:
    from apps.nikah import bot as nikah_bot
    from apps.payments import stars

    try:
        if 'pre_checkout_query' in update:
            stars.pre_checkout(update['pre_checkout_query'])
            return
        if 'callback_query' in update:
            cq = update['callback_query']
            text = nikah_bot.callback(cq) if (cq.get('data') or '').startswith('nk:') else ''
            api('answerCallbackQuery', {'callback_query_id': cq['id'], 'text': text or ''})
            return
        msg = update.get('message')
        if not msg:
            return
        chat = msg['chat']
        if msg.get('successful_payment'):
            stars.success(msg)
            return
        if chat.get('type') != 'private':
            if (msg.get('text') or '').startswith('/id'):
                reply(chat['id'], f'id этого чата: {chat["id"]}\nВпишите его в .env: TELEGRAM_MODERATION_CHAT_ID')
            return
        if msg.get('video_note') or msg.get('video'):
            nikah_bot.video_note(msg)
            return
        text = (msg.get('text') or '').strip()
        if text.startswith('/start'):
            param = text.split(maxsplit=1)[1] if ' ' in text else ''
            start(msg, param)
            return
        if text.startswith('/id'):
            reply(chat['id'], f'Ваш Telegram id: {msg["from"]["id"]}')
            return
        reply(chat['id'], 'Всё общение — внутри никяха. Нажмите «Открыть».', open_button('Открыть никях'))
    except Exception:
        log.exception('Ошибка обработки обновления Telegram: %s', update.get('update_id'))


def start(msg, param: str) -> None:
    from apps.nikah import bot as nikah_bot

    chat_id, tg_id = msg['chat']['id'], msg['from']['id']
    if param.startswith('ref_') and param[4:].isdigit():
        cache.set(f'tgref:{tg_id}', int(param[4:]), 30 * 86400)    # приглашение друга
    if param == 'verify' and nikah_bot.send_verify_instructions(tg_id):
        return
    markup = open_button('Открыть никях')
    reply(chat_id, WELCOME if markup else WELCOME + '\n\n(Администратору: задайте SITE_URL с https, чтобы появилась кнопка.)',
          markup)


def moderation_chat() -> str:
    return str(getattr(settings, 'TELEGRAM_MODERATION_CHAT_ID', '') or '')


def is_moderator(cq: dict) -> bool:
    chat_ok = str(cq.get('message', {}).get('chat', {}).get('id')) == moderation_chat() and moderation_chat()
    ids = getattr(settings, 'TELEGRAM_MODERATOR_IDS', [])
    return bool(chat_ok) and (not ids or cq.get('from', {}).get('id') in ids)
