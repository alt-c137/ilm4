"""Вложения чата: проверка, обработка, выдача только участникам диалога.

Фото — пересохраняются Pillow (без EXIF/геометок, ≤2048px, JPEG).
Голос и видеокружки — проверка по сигнатуре файла (а не по имени), лимиты
размера и длительности. Выдача — через view с проверкой участника и поддержкой
Range (без неё Safari не проигрывает аудио/видео); в проде можно отдать nginx
через X-Accel-Redirect (CHAT_XACCEL=True).
"""
import io
import mimetypes
import os
import re
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from django.utils.translation import gettext as _

LIMITS = {  # kind: (макс. байт, макс. секунд); для видео и файла предел — из «Настроек сайта»
    'photo': (10 * 1024 * 1024, None),
    'voice': (6 * 1024 * 1024, 300),
    'circle': (25 * 1024 * 1024, 60),
    'video': (None, 600),
    'file': (None, None),
}
# исполняемые файлы не принимаем: через чат их рассылают мошенники
BLOCKED_EXT = {'.exe', '.msi', '.bat', '.cmd', '.com', '.scr', '.pif', '.vbs', '.js', '.jse', '.wsf', '.ps1',
               '.jar', '.apk', '.app', '.dmg', '.sh', '.lnk', '.hta', '.cpl', '.reg'}


class MediaError(ValueError):
    pass


def _sniff(head: bytes) -> str:
    """Тип по первым байтам файла."""
    if head.startswith(b'\x1a\x45\xdf\xa3'):
        return 'webm'
    if head.startswith(b'OggS'):
        return 'ogg'
    if head[4:8] == b'ftyp':
        return 'mp4'
    if head.startswith(b'ID3') or head[:2] in (b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'):
        return 'mp3'
    return ''


def prepare(kind: str, upload, duration) -> tuple[ContentFile, int | None]:
    """Проверить и подготовить файл. Возвращает (файл, длительность)."""
    if kind not in LIMITS:
        raise MediaError(_('Неизвестный тип вложения'))
    max_bytes, max_sec = LIMITS[kind]
    if max_bytes is None:
        from .services import allowed_file_mb
        max_bytes = allowed_file_mb() * 1024 * 1024
    if upload.size > max_bytes:
        raise MediaError(_('Файл больше {v1} МБ').format(v1=max_bytes // (1024 * 1024)))
    name = uuid.uuid4().hex

    if kind == 'file':
        ext = os.path.splitext(upload.name or '')[1].lower()
        if ext in BLOCKED_EXT:
            raise MediaError(_('Такие файлы отправлять нельзя (программы и скрипты) — защита от вирусов.'))
        if upload.size == 0:
            raise MediaError(_('Файл пустой'))
        upload.name = f'{name}.bin'            # на диске — без исходного имени; имя хранится зашифрованным
        return upload, None

    if kind == 'photo':
        from PIL import Image, ImageOps
        try:
            img = Image.open(upload)
            img.verify()
            upload.seek(0)
            img = ImageOps.exif_transpose(Image.open(upload))
        except Exception as exc:
            raise MediaError(_('Это не изображение')) from exc
        img = img.convert('RGB')
        img.thumbnail((2048, 2048))
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=85, optimize=True)   # без EXIF — геометки не утекут
        return ContentFile(buf.getvalue(), name=f'{name}.jpg'), None

    head = upload.read(16)
    upload.seek(0)
    fmt = _sniff(head)
    allowed = {'voice': {'webm', 'ogg', 'mp4', 'mp3'}, 'circle': {'webm', 'mp4'}, 'video': {'webm', 'mp4'}}[kind]
    if fmt not in allowed:
        raise MediaError(_('Неподдерживаемый формат файла'))
    try:
        sec = max(0, min(int(float(duration or 0)), max_sec))
    except (TypeError, ValueError):
        sec = 0
    ext = {'webm': 'webm', 'ogg': 'ogg', 'mp4': 'mp4', 'mp3': 'mp3'}[fmt]
    upload.name = f'{name}.{ext}'              # не читаем в память: шифруется потоком (filecrypt.seal_file)
    return upload, sec


def content_type(path: str) -> str:
    path = path.removesuffix('.enc')                     # зашифрованный файл: тип — по исходному расширению
    ext = os.path.splitext(path)[1].lower()
    return {'.webm': 'video/webm', '.ogg': 'audio/ogg', '.mp4': 'video/mp4', '.mp3': 'audio/mpeg',
            '.jpg': 'image/jpeg'}.get(ext) or mimetypes.guess_type(path)[0] or 'application/octet-stream'


def _range(request, size):
    """(start, end) из заголовка Range или None; 'bad' — диапазон за пределами файла."""
    rng = re.match(r'bytes=(\d*)-(\d*)', request.headers.get('Range', ''))
    if not (rng and (rng.group(1) or rng.group(2))):
        return None
    start = int(rng.group(1)) if rng.group(1) else max(0, size - int(rng.group(2)))
    end = int(rng.group(2)) if rng.group(1) and rng.group(2) else size - 1
    end = min(end, size - 1)
    return 'bad' if start > end else (start, end)


def clean_name(name: str) -> str:
    """Имя файла для показа и скачивания: без путей и управляющих символов."""
    name = os.path.basename((name or '').replace('\\', '/')).strip()
    name = re.sub(r'[\x00-\x1f\x7f"<>|:*?]', '_', name)[:120]
    return name or 'file'


def serve_sealed(request, field_file, thread_id, download_name=''):
    """Зашифрованное вложение: расшифровываем только нужные куски (перемотка работает)."""
    from .filecrypt import FileCryptError, Reader
    path = field_file.path
    fh = open(path, 'rb')  # noqa: SIM115 — закрывается стримингом
    try:
        reader = Reader(thread_id, fh, os.path.getsize(path))
    except FileCryptError:
        fh.close()
        return HttpResponse(status=410)
    size = reader.size
    rng = _range(request, size)
    if rng == 'bad':
        fh.close()
        resp = HttpResponse(status=416)
        resp['Content-Range'] = f'bytes */{size}'
        return resp
    start, end = rng or (0, size - 1)

    def chunks():
        try:
            yield from reader.iter_range(start, end)
        except FileCryptError:
            return
        finally:
            fh.close()

    ctype = 'application/octet-stream' if download_name else content_type(field_file.name)
    resp = StreamingHttpResponse(chunks(), status=206 if rng else 200, content_type=ctype)
    if download_name:                               # «файлом»: только скачивание, браузер его не исполняет
        from urllib.parse import quote
        resp['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(download_name)}"
    if rng:
        resp['Content-Range'] = f'bytes {start}-{end}/{size}'
    resp['Content-Length'] = str(max(0, end - start + 1))
    resp['Accept-Ranges'] = 'bytes'
    resp['Cache-Control'] = 'private, no-store'      # расшифрованное не оседает в общих кешах
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp


def serve(request, field_file, thread_id=None, download_name=''):
    """Отдать файл с поддержкой Range (перемотка аудио/видео, Safari)."""
    if field_file.name.endswith('.enc') and thread_id is not None:
        return serve_sealed(request, field_file, thread_id, download_name)
    ctype = content_type(field_file.name)
    if getattr(settings, 'CHAT_XACCEL', False):
        resp = HttpResponse(content_type=ctype)
        resp['X-Accel-Redirect'] = '/protected-media/' + field_file.name
    else:
        path = field_file.path
        size = os.path.getsize(path)
        rng = re.match(r'bytes=(\d*)-(\d*)', request.headers.get('Range', ''))
        if rng and (rng.group(1) or rng.group(2)):
            start = int(rng.group(1)) if rng.group(1) else max(0, size - int(rng.group(2)))
            end = int(rng.group(2)) if rng.group(1) and rng.group(2) else size - 1
            end = min(end, size - 1)
            if start > end:
                resp = HttpResponse(status=416)
                resp['Content-Range'] = f'bytes */{size}'
                return resp
            f = open(path, 'rb')  # noqa: SIM115 — закрывается стримингом
            f.seek(start)
            length = end - start + 1

            def chunks(fh=f, left=length):
                try:
                    while left > 0:
                        data = fh.read(min(64 * 1024, left))
                        if not data:
                            break
                        left -= len(data)
                        yield data
                finally:
                    fh.close()

            resp = StreamingHttpResponse(chunks(), status=206, content_type=ctype)
            resp['Content-Range'] = f'bytes {start}-{end}/{size}'
            resp['Content-Length'] = str(length)
        else:
            resp = FileResponse(open(path, 'rb'), content_type=ctype)  # noqa: SIM115
        resp['Accept-Ranges'] = 'bytes'
    resp['Cache-Control'] = 'private, max-age=86400'
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp
