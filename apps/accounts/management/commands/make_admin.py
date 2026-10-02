"""Сделать человека главным администратором (суперадмином) сайта.

    python manage.py make_admin teacher@example.com
    python manage.py make_admin teacher@example.com --name "Устаз"
    python manage.py make_admin teacher@example.com --remove      # забрать права

Аккаунт с такой почтой уже есть — получает права. Нет — создаётся с временным паролем
(он печатается один раз; человек меняет его в профиле). При первом входе в админку сайт
попросит подключить двухшаговую защиту (приложение-аутентификатор) — так у всех сотрудников.
"""
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Выдать (или забрать) права суперадмина по email'

    def add_arguments(self, parser):
        parser.add_argument('email')
        parser.add_argument('--name', default='', help='имя для нового аккаунта')
        parser.add_argument('--remove', action='store_true', help='забрать права администратора')

    def handle(self, *args, **opts):
        User = get_user_model()
        email = opts['email'].strip().lower()
        if '@' not in email:
            raise CommandError('Нужен email, например teacher@example.com')
        user = User.objects.filter(email__iexact=email).first()
        if opts['remove']:
            if user is None:
                raise CommandError(f'Аккаунта {email} нет')
            user.is_staff = user.is_superuser = False
            user.save(update_fields=['is_staff', 'is_superuser'])
            self.stdout.write(self.style.SUCCESS(f'{email}: права администратора сняты'))
            return
        password = ''
        if user is None:
            password = secrets.token_urlsafe(9)
            username = email.split('@')[0][:120] + '_' + secrets.token_hex(2)
            user = User.objects.create_user(username, email, password, first_name=opts['name'][:150])
            self.stdout.write(f'Создан новый аккаунт {email}')
        user.is_staff = user.is_superuser = user.is_active = True
        user.save(update_fields=['is_staff', 'is_superuser', 'is_active'])
        from apps.accounts.audit import log_action
        log_action(None, 'Выданы права суперадмина (команда make_admin)', email)
        self.stdout.write(self.style.SUCCESS(f'{email} — теперь суперадмин.'))
        if password:
            self.stdout.write(f'Временный пароль: {password}\n(показывается один раз — передайте человеку лично, пусть сменит в профиле)')
        self.stdout.write('При первом входе в /admin/ сайт попросит подключить двухшаговую защиту.')
