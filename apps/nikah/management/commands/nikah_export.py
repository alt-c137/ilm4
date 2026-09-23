"""Выгрузить раздел «Никях» в архив для отдельной установки: python manage.py nikah_export nikah.zip"""
from django.core.management.base import BaseCommand

from apps.nikah.transfer import export_zip


class Command(BaseCommand):
    help = 'Никях → зашифрованный архив (нужен тот же CHAT_ENCRYPTION_KEY на новом сервере)'

    def add_arguments(self, parser):
        parser.add_argument('path')

    def handle(self, *args, path, **opts):
        counts = export_zip(path)
        self.stdout.write(self.style.SUCCESS(f'Готово: {path} — ' + ', '.join(f'{k}: {v}' for k, v in counts.items())))
