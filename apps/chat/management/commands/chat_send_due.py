"""Отправить запланированные сообщения, чьё время пришло. Сервис jobs запускает раз в минуту.

    python manage.py chat_send_due
"""
from django.core.management.base import BaseCommand

from apps.chat.services import deliver_due


class Command(BaseCommand):
    help = 'Отправить запланированные сообщения чата'

    def handle(self, *args, **opts):
        n = deliver_due()
        if n:
            self.stdout.write(f'Отправлено запланированных: {n}')
