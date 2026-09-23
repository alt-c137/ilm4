"""Раз в минуту (сервис jobs): закрыть просроченные показы фото и удалить фото из Telegram.
    python manage.py nikah_cleanup
"""
from django.core.management.base import BaseCommand

from apps.nikah.models import NikahMatch
from apps.nikah.services import cleanup_tg_photos, refresh


class Command(BaseCommand):
    help = 'Никях: истёкшие показы фото → отказ, удаление фото из Telegram'

    def handle(self, *args, **opts):
        n = 0
        qs = NikahMatch.objects.filter(stage=NikahMatch.PHOTOS) | NikahMatch.objects.exclude(
            sister_tg_msg=None, brother_tg_msg=None)
        for m in qs.select_related('sister__user', 'brother__user').distinct():
            refresh(m)
            cleanup_tg_photos(m)
            n += 1
        self.stdout.write(f'Проверено пар: {n}')
