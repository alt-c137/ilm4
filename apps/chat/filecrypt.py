"""Шифрование вложений чата (фото, видео, голос, кружки) ключом чата.

Файл шифруется кусками по 64 КБ (AES-256-GCM на каждый кусок): так можно отдать
любой фрагмент без расшифровки всего файла — перемотка видео и голосовых работает,
Safari получает свои Range-запросы.

Формат: ``ILM4F1`` (6 байт) | префикс nonce (8 байт) | куски.
Кусок: шифротекст 64 КБ (последний короче) + тег 16 байт.
Nonce куска = префикс (8) + номер куска (4 байта). AAD — чат, номер куска и признак
последнего куска: куски нельзя переставить, выкинуть или обрезать незаметно.
"""
import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .keyring import dek_for

MAGIC = b'ILM4F1'
HEADER = len(MAGIC) + 8
CHUNK = 64 * 1024
TAG = 16
SUFFIX = '.enc'


class FileCryptError(Exception):
    pass


def _aad(thread_id: int, index: int, last: bool) -> bytes:
    return f'ilm4:file:v1:thread:{thread_id}:chunk:{index}:last:{int(last)}'.encode()


def seal(thread_id: int, data: bytes) -> bytes:
    aes = AESGCM(dek_for(thread_id))
    prefix = os.urandom(8)
    out = [MAGIC, prefix]
    count = max(1, -(-len(data) // CHUNK))
    for i in range(count):
        piece = data[i * CHUNK:(i + 1) * CHUNK]
        out.append(aes.encrypt(prefix + struct.pack('>I', i), piece, _aad(thread_id, i, i == count - 1)))
    return b''.join(out)


def _read_exact(src, n: int) -> bytes:
    buf = b''
    while len(buf) < n:
        piece = src.read(n - len(buf))
        if not piece:
            break
        buf += piece
    return buf


def seal_file(thread_id: int, src, size: int):
    """Зашифровать поток (загруженный файл) без чтения целиком в память. Возвращает django File."""
    import tempfile

    from django.core.files import File
    aes = AESGCM(dek_for(thread_id))
    prefix = os.urandom(8)
    out = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)   # noqa: SIM115 — закроет Django после сохранения
    out.write(MAGIC + prefix)
    count = max(1, -(-size // CHUNK))
    for i in range(count):
        piece = _read_exact(src, CHUNK)
        out.write(aes.encrypt(prefix + struct.pack('>I', i), piece, _aad(thread_id, i, i == count - 1)))
    out.seek(0)
    return File(out)


def plain_size(enc_size: int) -> int:
    body = enc_size - HEADER
    count = max(1, -(-body // (CHUNK + TAG)))
    return body - TAG * count


class Reader:
    """Чтение расшифрованных байтов [start, end] из зашифрованного файла."""

    def __init__(self, thread_id: int, fh, enc_size: int):
        self.fh, self.thread_id = fh, thread_id
        head = fh.read(HEADER)
        if head[:len(MAGIC)] != MAGIC:
            raise FileCryptError('не зашифрованный файл ilm4')
        self.prefix = head[len(MAGIC):]
        self.size = plain_size(enc_size)
        self.count = max(1, -(-self.size // CHUNK))
        dek = dek_for(thread_id, create=False)
        if dek is None:
            raise FileCryptError('нет ключа чата')
        self.aes = AESGCM(dek)

    def _chunk(self, i: int) -> bytes:
        self.fh.seek(HEADER + i * (CHUNK + TAG))
        raw = self.fh.read(CHUNK + TAG)
        try:
            return self.aes.decrypt(self.prefix + struct.pack('>I', i), raw,
                                    _aad(self.thread_id, i, i == self.count - 1))
        except InvalidTag as exc:
            raise FileCryptError('файл повреждён или подменён') from exc

    def iter_range(self, start: int, end: int):
        """Байты [start, end] включительно, по кускам (без загрузки файла целиком в память)."""
        if self.size == 0:
            return
        first, last = start // CHUNK, end // CHUNK
        for i in range(first, last + 1):
            data = self._chunk(i)
            lo = start - i * CHUNK if i == first else 0
            hi = end - i * CHUNK + 1 if i == last else len(data)
            yield data[lo:hi]


def is_sealed(name: str) -> bool:
    return name.endswith(SUFFIX)
