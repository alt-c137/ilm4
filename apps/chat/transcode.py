"""Сжатие видео в чате — как делает Telegram: «видео» пережимается, «файлом» уходит как есть.

После загрузки видео сервер в фоне перекодирует его в MP4 (H.264 + AAC) с высотой не больше
настройки «качество видео» (по умолчанию 720p). Итог: файл в несколько раз меньше, быстрее
открывается по мобильной сети и проигрывается на любом телефоне (в т.ч. .mov с iPhone).
Исходник после этого не хранится; нужен оригинал — «Отправить файлом».

ffmpeg берётся из пакета imageio-ffmpeg (ставится вместе с сайтом) или системный.
Нет ffmpeg или сжатие не удалось — остаётся загруженный файл, чат не ломается.
"""
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading

from django.db import transaction

log = logging.getLogger(__name__)
TIMEOUT = 15 * 60


def ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:                                   # noqa: BLE001 — пакета нет или нет бинарника под платформу
        return shutil.which('ffmpeg') or ''


def schedule(message_id: int) -> None:
    """Запустить сжатие после сохранения сообщения, в отдельном потоке (ответ человеку не ждёт)."""
    from django.conf import settings
    if getattr(settings, 'CHAT_TRANSCODE', True):
        transaction.on_commit(lambda: threading.Thread(target=_safe, args=(message_id,), daemon=True).start())


def _safe(message_id: int) -> None:
    from django.db import connection
    try:
        compress(message_id)
    except Exception:
        log.exception('Не удалось сжать видео сообщения %s', message_id)
    finally:
        connection.close()


def probe(path: str) -> dict:
    """Ширина, высота и длительность из вывода ffmpeg (ffprobe в комплект не входит)."""
    out = subprocess.run([ffmpeg_path(), '-hide_banner', '-i', path], capture_output=True, text=True,
                         timeout=60, check=False).stderr
    size = re.search(r'Video:.*?(\d{2,5})x(\d{2,5})', out)
    dur = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', out)
    rot = re.search(r'rotation of (-?\d+)', out)
    w, h = (int(size.group(1)), int(size.group(2))) if size else (0, 0)
    if rot and abs(int(rot.group(1))) in (90, 270):
        w, h = h, w                                     # вертикальное видео с телефона
    seconds = (int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3))) if dur else 0
    return {'width': w, 'height': h, 'seconds': seconds}


def compress(message_id: int) -> bool:
    """Перекодировать видео сообщения. True — файл заменён сжатым."""
    from apps.core.models import SiteSettings

    from .filecrypt import SUFFIX, Reader, is_sealed, seal_file
    from .models import Message

    exe = ffmpeg_path()
    msg = Message.objects.filter(pk=message_id, kind=Message.VIDEO).first()
    if not exe or msg is None or not msg.attachment or not is_sealed(msg.attachment.name):
        return False
    target = SiteSettings.get_solo().chat_video_height
    old_name, old_path = msg.attachment.name, msg.attachment.path
    with tempfile.TemporaryDirectory(prefix='ilm4-video-') as tmp:
        src, dst = os.path.join(tmp, 'in'), os.path.join(tmp, 'out.mp4')
        with open(old_path, 'rb') as fh, open(src, 'wb') as plain:        # расшифрованная копия живёт только в tmp
            reader = Reader(msg.thread_id, fh, os.path.getsize(old_path))
            plain.writelines(reader.iter_range(0, max(0, reader.size - 1)))
        info = probe(src)
        short_side = min(info['width'], info['height']) or target
        scale = f"scale='if(gt(iw,ih),-2,{target})':'if(gt(iw,ih),{target},-2)'" if short_side > target else 'scale=trunc(iw/2)*2:trunc(ih/2)*2'
        cmd = [exe, '-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-vf', scale,
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-pix_fmt', 'yuv420p',
               '-c:a', 'aac', '-b:a', '96k', '-ac', '2', '-movflags', '+faststart', '-map_metadata', '-1', dst]
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, check=False)
        if done.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) == 0:
            log.warning('ffmpeg не справился с видео %s: %s', message_id, done.stderr[-400:])
            return False
        new_size, old_size = os.path.getsize(dst), os.path.getsize(src)
        already_mp4 = old_name.endswith('.mp4' + SUFFIX)
        if already_mp4 and short_side <= target and new_size >= old_size * 0.9:
            return False                                # и так небольшое — оставляем как есть
        with open(dst, 'rb') as out:
            sealed = seal_file(msg.thread_id, out, new_size)
            new_name = os.path.basename(old_name).split('.')[0] + '.mp4' + SUFFIX
            fresh = Message.objects.filter(pk=message_id).first()
            if fresh is None:                           # сообщение удалили, пока шло сжатие
                return False
            fresh.attachment.save(new_name, sealed, save=False)
            if info['seconds'] and not fresh.duration:
                fresh.duration = int(info['seconds'])
            fresh.save(update_fields=['attachment', 'duration'])
    try:
        os.remove(old_path)                             # несжатый исходник больше не хранится
    except OSError:
        pass
    return True
