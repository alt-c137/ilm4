"""Единый формат сообщения для WebSocket и HTTP (текст и вложения)."""
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _lazy


def message_payload(m) -> dict:
    from . import contexts
    from .media import is_risky_name
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
        'file_risky': bool(meta) and is_risky_name(meta.get('name', '')),
        # признаки мошенничества (предоплата, перевод на карту) — получателю покажем предупреждение
        'warn': m.kind != 'system' and contexts.risky(m.thread) and contexts.is_scam(m.body),
        'silent': m.silent,
        'room': m.thread.kind if m.thread.is_room else '',     # группа / канал: показываем имя автора и просмотры
        'views': m.views if m.thread.is_channel else 0,
        'hue': m.sender_id % 7,
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
    from .richtext import plain
    return PREVIEW.get(m.kind, '') or plain(m.body)


def notify_recipients(thread, sender, text, silent: bool = False):
    """Колокольчик и пуш получателю (кроме отправителя). «Без звука» — пуш без звука."""
    from apps.core.models import Notification

    from .models import Member

    msg = f'{sender.get_display_name()}: {text[:80]}'
    # «без звука» у этого диалога (кнопка «Звук» в профиле собеседника) — уведомление придёт тихо
    muted = set(Member.objects.filter(thread=thread, muted=True).values_list('user_id', flat=True))
    for participant in thread.participants.exclude(pk=sender.pk):
        Notification.objects.create(user=participant, text=msg, url=f'/chat/{thread.pk}/',
                                    silent=silent or participant.pk in muted)
