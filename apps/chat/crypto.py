"""Шифрование переписки «в покое» (at rest): текст сообщений хранится в БД
зашифрованным (Fernet = AES-128-CBC + HMAC-SHA256).

Ключ — CHAT_ENCRYPTION_KEY в .env (Fernet.generate_key()). Если не задан —
выводится из SECRET_KEY (удобно в деве; в проде задайте отдельный ключ и
храните его копию: потеря ключа = потеря переписки).

Это защищает от утечки базы и бэкапов. Сквозное шифрование «как секретные
чаты Telegram» (ключи только на устройствах) — отдельная фаза, см. docs/ROADMAP.md.
"""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

PREFIX = 'enc1:'


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = getattr(settings, 'CHAT_ENCRYPTION_KEY', '') or ''
    if not key:
        digest = hashlib.sha256(('ilm4-chat:' + settings.SECRET_KEY).encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(text: str) -> str:
    if not text or text.startswith(PREFIX):
        return text
    return PREFIX + _fernet().encrypt(text.encode()).decode()


def decrypt(value: str) -> str:
    if not value or not value.startswith(PREFIX):
        return value  # старые (незашифрованные) записи читаются как есть
    try:
        return _fernet().decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken:
        return '[сообщение не удалось расшифровать]'


def encrypt_bytes(data: bytes) -> bytes:
    """Файлы (фото анкет никяха) — тем же ключом, что и переписка."""
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _fernet().decrypt(token)


class EncryptedTextField(models.TextField):
    """TextField, который шифрует при записи и расшифровывает при чтении."""

    def from_db_value(self, value, expression, connection):
        return decrypt(value) if isinstance(value, str) else value

    def to_python(self, value):
        return decrypt(value) if isinstance(value, str) else value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt(value) if isinstance(value, str) else value
