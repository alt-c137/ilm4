"""Ключи переписки (docs/MESSENGER.md §2.1).

    manage.py chat_keys status     — какой главный ключ текущий, сколько чатов на каком
    manage.py chat_keys generate   — новый главный ключ (строка для CHAT_MASTER_KEYS)
    manage.py chat_keys rotate     — перешифровать ключи чатов текущим главным ключом
    manage.py chat_keys migrate    — перевести старую переписку (enc1/без шифра) и файлы на новый формат
    manage.py chat_keys split      — резервная копия главного ключа: 3 части, любые 2 восстанавливают
    manage.py chat_keys join A B   — собрать главный ключ из частей (аварийное восстановление)

Смена главного ключа:
  1) generate → вписать новый ключ ПЕРВЫМ: CHAT_MASTER_KEYS=k2:<новый>,k1:<старый>
  2) перезапустить сервер, затем rotate
  3) убрать старый ключ из CHAT_MASTER_KEYS, перезапустить, сделать split для нового.
"""
import os

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone

from apps.chat import keyring, shamir


class Command(BaseCommand):
    help = 'Ключи переписки: status, generate, rotate, migrate, split, join'

    def add_arguments(self, parser):
        parser.add_argument('action', choices=['status', 'generate', 'rotate', 'migrate', 'split', 'join'])
        parser.add_argument('shares', nargs='*', help='части ключа (для join)')
        parser.add_argument('--threshold', type=int, default=2)
        parser.add_argument('--parts', type=int, default=3)
        parser.add_argument('--kid', default='', help='имя ключа для generate (по умолчанию k + дата)')

    def handle(self, action, shares, threshold, parts, kid, **opts):
        getattr(self, f'do_{action}')(shares=shares, threshold=threshold, parts=parts, kid=kid)

    def do_status(self, **_):
        from apps.chat.models import Message, ThreadKey
        keys = keyring.master_keys()
        self.stdout.write(f'Главные ключи: {", ".join(keys)} (текущий: {keyring.current_kid()})')
        if 'dev' in keys:
            self.stdout.write(self.style.WARNING('Ключ «dev» выведен из SECRET_KEY — только для разработки.'))
        for row in ThreadKey.objects.values('kid').annotate(n=Count('pk')):
            self.stdout.write(f'  чатов на ключе {row["kid"]}: {row["n"]}')
        old = Message.objects.exclude(body_enc='').exclude(body_enc__startswith=keyring.PREFIX).count()
        files = Message.objects.exclude(attachment='').exclude(attachment__endswith='.enc').count()
        self.stdout.write(f'Сообщений в старом формате: {old}; незашифрованных файлов: {files}'
                          + (' — выполните chat_keys migrate' if old or files else ''))

    def do_generate(self, kid='', **_):
        kid = kid or 'k' + timezone.now().strftime('%Y%m%d')
        self.stdout.write(f'{kid}:{keyring.generate_master_key()}')
        self.stdout.write(self.style.WARNING(
            'Впишите в .env ПЕРВЫМ в CHAT_MASTER_KEYS, сразу сделайте резервную копию (chat_keys split) '
            'и не храните ключ рядом с бэкапом базы.'))

    def do_rotate(self, **_):
        from apps.chat.models import ThreadKey
        cur = keyring.current_kid()
        n = 0
        for row in ThreadKey.objects.exclude(kid=cur).iterator():
            dek = keyring.unwrap(row.thread_id, row.wrapped)
            row.wrapped, row.kid, row.rotated_at = keyring.wrap(row.thread_id, dek, cur), cur, timezone.now()
            row.save(update_fields=['wrapped', 'kid', 'rotated_at'])
            n += 1
        self.stdout.write(self.style.SUCCESS(f'Перешифровано ключей чатов: {n}. Старый главный ключ можно убрать.'))

    def do_migrate(self, **_):
        from apps.chat.crypto import decrypt as legacy
        from apps.chat.filecrypt import SUFFIX, seal
        from apps.chat.models import Message
        texts = files = 0
        qs = Message.objects.exclude(body_enc='').exclude(body_enc__startswith=keyring.PREFIX)
        for m in qs.iterator():
            m.body = legacy(m.body_enc)
            m.save(update_fields=['body'])
            texts += 1
        for m in Message.objects.exclude(attachment='').exclude(attachment__endswith=SUFFIX).iterator():
            try:
                with m.attachment.open('rb') as f:
                    data = f.read()
            except FileNotFoundError:
                continue
            old = m.attachment.name
            m.attachment.save(os.path.basename(old) + SUFFIX, ContentFile(seal(m.thread_id, data)), save=False)
            m.save(update_fields=['attachment'])
            m.attachment.storage.delete(old)            # открытая копия больше не нужна
            files += 1
        self.stdout.write(self.style.SUCCESS(f'Переведено на новый формат: сообщений {texts}, файлов {files}.'))

    def do_split(self, threshold=2, parts=3, **_):
        kid = keyring.current_kid()
        if kid == 'dev':
            raise CommandError('Сначала задайте настоящий CHAT_MASTER_KEYS (chat_keys generate).')
        key = keyring.master_keys()[kid]
        self.stdout.write(f'Главный ключ «{kid}»: {parts} части, восстановить — любые {threshold}.\n')
        for share in shamir.split(key, threshold, parts):
            self.stdout.write(f'  {kid}:{share}')
        self.stdout.write(self.style.WARNING(
            '\nКаждую часть — в своё место: флешка в сейфе, менеджер паролей, второй доверенный человек. '
            'Одна часть ничего не раскрывает. Не храните части вместе и рядом с бэкапом базы.'))

    def do_join(self, shares=(), **_):
        if len(shares) < 2:
            raise CommandError('Укажите минимум две части: chat_keys join <часть1> <часть2>')
        kids = {s.split(':', 1)[0] for s in shares}
        if len(kids) != 1:
            raise CommandError('Части от разных ключей')
        try:
            key = shamir.combine([s.split(':', 1)[1] for s in shares])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f'{kids.pop()}:{keyring.b64e(key)}')
