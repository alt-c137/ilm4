"""Напоминания трекера привычек. Запускать раз в минуту (сервис jobs / cron):

    python manage.py tracker_remind
"""
from django.core.management.base import BaseCommand
from django.utils import translation
from django.utils.translation import gettext as _

from apps.core.models import Notification
from apps.tracker.services import due_reminders


class Command(BaseCommand):
    help = 'Отправить напоминания о привычках, время которых наступило'

    def handle(self, *args, **opts):
        n = 0
        for user, habit in due_reminders():
            with translation.override(user.language or 'ru'):
                text = _('{emoji} Пора: {title}').format(emoji=habit.emoji, title=habit.title)
            Notification.objects.create(user=user, text=text, url='/tracker/')
            n += 1
        self.stdout.write(f'напоминаний: {n}')
