"""Автопринятие безопасных сделок. Запускать по расписанию (cron / systemd timer), например раз в час:
    python manage.py release_due_deals
"""
from django.core.management.base import BaseCommand

from apps.deals.services import release_due


class Command(BaseCommand):
    help = 'Выплатить исполнителям по сделкам, где заказчик не ответил в срок автопринятия'

    def handle(self, *args, **opts):
        self.stdout.write(f'Автопринято сделок: {release_due()}')
