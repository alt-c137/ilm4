"""Единый формат сообщения для WebSocket и HTTP (текст и вложения)."""
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _lazy


def message_payload(m) -> dict:
    from . import contexts
    local = timezone.localtime(m.created_at)   # время в зоне проекта, не UTC
    meta = m.meta if m.kind == 'file' else {}
    return {
        'id': m.pk,
        'sender_id': m.sender_id,
        'sender_name': m.sender.get_display_name(),
        'kind': m.kind,
        'body': m.body,
        'url': reverse('chat:file', args=[m.pk]) if m.attachment else '',
        'duration': m.duration or 0,
        'created_at': local.strftime('%d.%m %H:%M'),
        'time': local.strftime('%H:%M'),
        'day': local.date().isoformat(),
        'file_name': meta.get('name', ''),
        'file_size': meta.get('size', 0),
        # признаки мошенничества (предоплата, перевод на карту) — получателю покажем предупреждение
        'warn': m.kind != 'system' and contexts.risky(m.thread) and contexts.is_scam(m.body),
        'silent': m.silent,
        'scheduled': bool(m.scheduled_at),
        'scheduled_at': timezone.localtime(m.scheduled_at).isoformat() if m.scheduled_at else '',
        'scheduled_label': timezone.localtime(m.scheduled_at).strftime('%d.%m %H:%M') if m.scheduled_at else '',
    }


PREVIEW = {'photo': _lazy('Фото'), 'video': _lazy('Видео'), 'voice': _lazy('Голосовое сообщение'),
           'circle': _lazy('Видеосообщение'), 'file': _lazy('Файл')}


def preview(m) -> str:
    """Текст для списка чатов и уведомлений."""
    if m.kind == 'file':
        return m.meta.get('name') or str(PREVIEW['file'])
    return PREVIEW.get(m.kind, '') or m.body


def notify_recipients(thread, sender, text, silent: bool = False):
    """Колокольчик и пуш получателю (кроме отправителя). «Без звука» — пуш без звука."""
    from apps.core.models import Notification

    msg = f'{sender.get_display_name()}: {text[:80]}'
    for participant in thread.participants.exclude(pk=sender.pk):
        Notification.objects.create(user=participant, text=msg, url=f'/chat/{thread.pk}/', silent=silent)
