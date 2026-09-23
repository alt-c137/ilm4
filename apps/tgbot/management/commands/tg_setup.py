"""Настроить бота одной командой: кнопка меню «Никях», команды, вебхук.
    python manage.py tg_setup              # ПК: кнопка меню + опрос (затем manage.py tg_bot)
    python manage.py tg_setup --webhook    # сервер: Telegram шлёт обновления на SITE_URL/tg/webhook/
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.telegram import api, bot_token, webapp_url


class Command(BaseCommand):
    help = 'Настройка Telegram-бота: меню, команды, вебхук'

    def add_arguments(self, parser):
        parser.add_argument('--webhook', action='store_true', help='включить вебхук (для сервера)')

    def handle(self, *args, webhook=False, **opts):
        if not bot_token():
            raise CommandError('Нет TELEGRAM_BOT_TOKEN в .env')
        me = api('getMe')
        if not me:
            raise CommandError('Telegram не принял токен — проверьте TELEGRAM_BOT_TOKEN')
        url = webapp_url('/nikah/')
        if not url:
            raise CommandError('Нужен SITE_URL с https:// (на ПК — адрес туннеля, см. КАК_ЗАПУСТИТЬ.md)')
        api('setMyCommands', {'commands': [{'command': 'start', 'description': 'Открыть никях'}]})
        api('setChatMenuButton', {'menu_button': {'type': 'web_app', 'text': 'Никях', 'web_app': {'url': url}}})
        if webhook:
            secret = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '')
            if not secret:
                raise CommandError('Для вебхука задайте TELEGRAM_WEBHOOK_SECRET в .env')
            ok = api('setWebhook', {'url': webapp_url('/tg/webhook/'), 'secret_token': secret,
                                    'allowed_updates': ['message', 'callback_query', 'pre_checkout_query']})
            self.stdout.write(f'Вебхук: {"включён" if ok else "ОШИБКА"}')
        else:
            api('deleteWebhook')
            self.stdout.write('Вебхук выключен — запустите: python manage.py tg_bot')
        self.stdout.write(self.style.SUCCESS(f'Готово: @{me["username"]}, кнопка меню → {url}'))
