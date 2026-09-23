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

LIMITS = {  # kind: (макс. байт, макс. секунд)
    'photo': (10 * 1024 * 1024, None),
    'voice': (6 * 1024 * 1024, 300),
    'circle': (25 * 1024 * 1024, 60),
}


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
        raise MediaError('Неизвестный тип вложения')
    max_bytes, max_sec = LIMITS[kind]
    if upload.size > max_bytes:
        raise MediaError(f'Файл больше {max_bytes // (1024 * 1024)} МБ')
    name = uuid.uuid4().hex

    if kind == 'photo':
        from PIL import Image, ImageOps
        try:
            img = Image.open(upload)
            img.verify()
            upload.seek(0)
            img = ImageOps.exif_transpose(Image.open(upload))
        except Exception as exc:
            raise MediaError('Это не изображение') from exc
        img = img.convert('RGB')
        img.thumbnail((2048, 2048))
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=85, optimize=True)   # без EXIF — геометки не утекут
        return ContentFile(buf.getvalue(), name=f'{name}.jpg'), None

    head = upload.read(16)
    upload.seek(0)
    fmt = _sniff(head)
    allowed = {'voice': {'webm', 'ogg', 'mp4', 'mp3'}, 'circle': {'webm', 'mp4'}}[kind]
    if fmt not in allowed:
        raise MediaError('Неподдерживаемый формат файла')
    try:
        sec = max(0, min(int(float(duration or 0)), max_sec))
    except (TypeError, ValueError):
        sec = 0
    ext = {'webm': 'webm', 'ogg': 'ogg', 'mp4': 'mp4', 'mp3': 'mp3'}[fmt]
    return ContentFile(upload.read(), name=f'{name}.{ext}'), sec


def content_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {'.webm': 'video/webm', '.ogg': 'audio/ogg', '.mp4': 'video/mp4', '.mp3': 'audio/mpeg',
            '.jpg': 'image/jpeg'}.get(ext) or mimetypes.guess_type(path)[0] or 'application/octet-stream'


def serve(request, field_file):
    """Отдать файл с поддержкой Range (перемотка аудио/видео, Safari)."""
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
