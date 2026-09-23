"""Бот на ПК без внешнего адреса: опрашивает Telegram сам (long polling).
    python manage.py tg_bot
На сервере не нужен — там вебхук (python manage.py tg_setup --webhook)."""
import time

import requests
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.telegram import api, bot_token
from apps.tgbot.dispatch import handle_update


class Command(BaseCommand):
    help = 'Telegram-бот в режиме опроса (для ПК)'

    def handle(self, *args, **opts):
        token = bot_token()
        if not token:
            raise CommandError('Нет TELEGRAM_BOT_TOKEN в .env')
        me = api('getMe') or {}
        api('deleteWebhook')   # опрос и вебхук одновременно не работают
        self.stdout.write(self.style.SUCCESS(f'Бот @{me.get("username", "?")} слушает. Остановить — Ctrl+C'))
        offset = 0
        while True:
            try:
                r = requests.get(f'https://api.telegram.org/bot{token}/getUpdates',
                                 params={'offset': offset, 'timeout': 25}, timeout=35).json()
            except (requests.RequestException, ValueError):
                time.sleep(3)
                continue
            for update in r.get('result', []):
                offset = update['update_id'] + 1
                handle_update(update)
