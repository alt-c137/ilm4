"""Ключи переписки: главный ключ (KEK) → ключ чата (DEK) → сообщения и файлы.

Схема «матрёшка» (envelope encryption), как в облачных чатах Telegram и у крупных
сервисов (OWASP Cryptographic Storage):

* у каждого диалога свой случайный 256-битный ключ (DEK); в базе он лежит только
  зашифрованным главным ключом (`ThreadKey.wrapped`);
* главный ключ (KEK) — в `CHAT_MASTER_KEYS` (.env / хранилище ключей), в базе его нет;
  украденная база без главного ключа — набор случайных байтов;
* шифр — AES-256-GCM (шифрование + защита от подделки); AAD привязывает шифротекст
  к конкретному чату, его нельзя «переставить» в чужой диалог.

Формат текста сообщения: ``enc2:<base64(nonce12 | ciphertext+tag)>``.
Формат обёрнутого ключа: ``<kid>.<base64(nonce12 | ciphertext+tag)>``.
Смена главного ключа и деление его на части — `manage.py chat_keys` (docs/MESSENGER.md).
"""
import base64
import hashlib
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext as _

PREFIX = 'enc2:'
NONCE = 12
KEY_BYTES = 32


class KeyringError(Exception):
    """Ключ не найден или данные повреждены."""


def b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def generate_master_key() -> str:
    return b64e(os.urandom(KEY_BYTES))


@lru_cache(maxsize=1)
def master_keys() -> dict:
    """{kid: ключ}, первый — текущий. Без настройки (разработка) — ключ из SECRET_KEY."""
    raw = (getattr(settings, 'CHAT_MASTER_KEYS', '') or '').strip()
    keys = {}
    for part in filter(None, (p.strip() for p in raw.split(','))):
        kid, _sep, value = part.partition(':')
        key = b64d(value) if value else b''
        if not kid or len(key) != KEY_BYTES:
            raise ImproperlyConfigured('CHAT_MASTER_KEYS: формат "kid:<base64 32 байта>,…" '
                                       '(новый ключ: manage.py chat_keys generate)')
        keys[kid] = key
    if not keys:
        keys['dev'] = hashlib.sha256(('ilm4-chat-kek:' + settings.SECRET_KEY).encode()).digest()
    return keys


def current_kid() -> str:
    return next(iter(master_keys()))


def _aad_dek(thread_id: int) -> bytes:
    return f'ilm4:dek:v1:thread:{thread_id}'.encode()


def _aad_msg(thread_id: int) -> bytes:
    return f'ilm4:msg:v1:thread:{thread_id}'.encode()


def wrap(thread_id: int, dek: bytes, kid: str | None = None) -> str:
    kid = kid or current_kid()
    nonce = os.urandom(NONCE)
    return f'{kid}.' + b64e(nonce + AESGCM(master_keys()[kid]).encrypt(nonce, dek, _aad_dek(thread_id)))


def unwrap(thread_id: int, wrapped: str) -> bytes:
    kid, _sep, body = wrapped.partition('.')
    key = master_keys().get(kid)
    if key is None:
        raise KeyringError(f'нет главного ключа "{kid}" в CHAT_MASTER_KEYS')
    raw = b64d(body)
    try:
        return AESGCM(key).decrypt(raw[:NONCE], raw[NONCE:], _aad_dek(thread_id))
    except InvalidTag as exc:
        raise KeyringError('ключ чата повреждён или главный ключ не тот') from exc


# Кеш расшифрованных ключей чатов в памяти процесса (не в базе и не в Redis).
_DEK_CACHE: dict[int, bytes] = {}
_DEK_CACHE_MAX = 2048


def dek_for(thread_id: int, create: bool = True) -> bytes | None:
    """Ключ чата: из кеша, из базы или новый (при первом сообщении/файле)."""
    dek = _DEK_CACHE.get(thread_id)
    if dek is not None:
        return dek
    from .models import ThreadKey
    row = ThreadKey.objects.filter(thread_id=thread_id).first()
    if row is None:
        if not create:
            return None
        dek = os.urandom(KEY_BYTES)
        row, made = ThreadKey.objects.get_or_create(thread_id=thread_id, defaults={
            'wrapped': wrap(thread_id, dek), 'kid': current_kid()})
        if not made:                        # параллельный запрос успел раньше — берём его ключ
            dek = unwrap(thread_id, row.wrapped)
    else:
        dek = unwrap(thread_id, row.wrapped)
    if len(_DEK_CACHE) >= _DEK_CACHE_MAX:
        _DEK_CACHE.pop(next(iter(_DEK_CACHE)))
    _DEK_CACHE[thread_id] = dek
    return dek


def forget_cache() -> None:
    _DEK_CACHE.clear()
    master_keys.cache_clear()


def encrypt_text(thread_id: int, text: str) -> str:
    if not text:
        return ''
    nonce = os.urandom(NONCE)
    return PREFIX + b64e(nonce + AESGCM(dek_for(thread_id)).encrypt(nonce, text.encode(), _aad_msg(thread_id)))


def decrypt_text(thread_id: int, value: str) -> str:
    """enc2 (новый формат), enc1 (старый Fernet) или незашифрованный (самые старые записи)."""
    if not value:
        return ''
    if value.startswith(PREFIX):
        raw = b64d(value[len(PREFIX):])
        try:
            dek = dek_for(thread_id, create=False)
            if dek is None:
                raise KeyringError('нет ключа чата')
            return AESGCM(dek).decrypt(raw[:NONCE], raw[NONCE:], _aad_msg(thread_id)).decode()
        except (InvalidTag, KeyringError):
            return _('[сообщение не удалось расшифровать]')
    from .crypto import decrypt as legacy_decrypt
    return legacy_decrypt(value)
