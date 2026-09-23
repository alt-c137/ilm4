"""Загрузить архив никяха в эту установку: python manage.py nikah_import nikah.zip"""
from django.core.management.base import BaseCommand, CommandError

from apps.nikah.transfer import import_zip


class Command(BaseCommand):
    help = 'Архив nikah_export → эта база (аккаунты сопоставляются по email)'

    def add_arguments(self, parser):
        parser.add_argument('path')

    def handle(self, *args, path, **opts):
        from cryptography.fernet import InvalidToken
        try:
            report = import_zip(path)
        except InvalidToken:
            raise CommandError('Не удалось расшифровать: на этом сервере другой CHAT_ENCRYPTION_KEY') from None
        self.stdout.write(self.style.SUCCESS('Импорт: ' + ', '.join(f'{k}: {v}' for k, v in report.items())))
