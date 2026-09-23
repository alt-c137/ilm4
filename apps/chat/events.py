"""Единый формат сообщения для WebSocket и HTTP (текст и вложения)."""
from django.urls import reverse
from django.utils import timezone


def message_payload(m) -> dict:
    local = timezone.localtime(m.created_at)   # время в зоне проекта, не UTC
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
    }


PREVIEW = {'photo': 'Фото', 'voice': 'Голосовое сообщение', 'circle': 'Видеосообщение'}


def preview(m) -> str:
    """Текст для списка чатов и уведомлений."""
    return PREVIEW.get(m.kind, '') or m.body


def notify_recipients(thread, sender, text):
    """Колокольчик получателю (кроме отправителя)."""
    from apps.core.models import Notification

    msg = f'{sender.get_display_name()}: {text[:80]}'
    for participant in thread.participants.exclude(pk=sender.pk):
        Notification.objects.create(user=participant, text=msg, url=f'/chat/{thread.pk}/')
