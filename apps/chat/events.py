"""Единый формат сообщения для WebSocket и HTTP (текст и вложения)."""
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _lazy

from . import persona


def reply_brief(m) -> dict | None:
    """Коротко о сообщении, на которое отвечают (полоска с именем и началом текста, как в Telegram)."""
    if m is None:
        return None
    return {'id': m.pk, 'name': persona.name_by_thread_id(m.thread_id, m.sender), 'kind': m.kind, 'text': str(preview(m))[:120],
            'hue': m.sender_id % 7}


def reactions_of(m) -> list:
    """[{'e': '👍', 'n': 3}] — сначала самые частые."""
    from django.db.models import Count
    rows = m.reactions.values('emoji').annotate(n=Count('id')).order_by('-n', 'emoji')
    return [{'e': r['emoji'], 'n': r['n']} for r in rows]


def decorate(msgs, user=None) -> None:
    """Разом подгрузить реакции (и свою) для пачки сообщений — без запроса на каждое."""
    from collections import defaultdict

    from django.db.models import Count

    from .models import Reaction
    ids = [m.pk for m in msgs]
    if not ids:
        return
    table = defaultdict(list)
    for r in (Reaction.objects.filter(message__in=ids).values('message_id', 'emoji').annotate(n=Count('id'))
              .order_by('-n', 'emoji')):
        table[r['message_id']].append({'e': r['emoji'], 'n': r['n']})
    mine = {}
    if user is not None and getattr(user, 'pk', None):
        mine = dict(Reaction.objects.filter(message__in=ids, user=user).values_list('message_id', 'emoji'))
    # галочки в группе — как в Telegram: ✓ отправлено, ✓✓ — прочитал хотя бы один участник (кроме автора)
    until = {}
    if user is not None and getattr(user, 'pk', None):
        from django.db.models import Max

        from .models import Member, Thread
        groups = {m.thread_id for m in msgs if m.sender_id == user.pk and getattr(m, 'thread', None) is not None and m.thread.kind == Thread.GROUP}
        if groups:
            until = dict(Member.objects.filter(thread__in=groups).exclude(user=user).exclude(role=Member.BANNED)
                         .values('thread_id').annotate(u=Max('last_read_at')).values_list('thread_id', 'u'))
    for m in msgs:
        m._rx, m._my = table.get(m.pk, []), mine.get(m.pk, '')
        u = until.get(m.thread_id)
        m._room_read = bool(u and m.created_at <= u)


def message_payload(m) -> dict:
    from . import contexts
    from .media import is_risky_name
    local = timezone.localtime(m.created_at)   # время в зоне проекта, не UTC
    meta = m.meta if m.kind in ('file', 'photo') and m.meta_enc else {}
    rx = m.__dict__.get('_rx')
    if rx is None:
        rx = reactions_of(m) if m.pk else []
    fwd = m.fwd if m.fwd_enc else None
    return {
        'reply': reply_brief(m.reply_to) if m.reply_to_id else None,
        'fwd': fwd,
        'edited': bool(m.edited_at),
        'pinned': bool(m.pinned_at),
        'reactions': rx,
        'my_reaction': m.__dict__.get('_my', ''),
        'comment_of': m.comment_of_id,
        'comments': m.comments_count,
        'read': bool(m.read_at) or bool(m.__dict__.get('_room_read')),
        'iso': m.created_at.isoformat(),
        'id': m.pk,
        'thread': m.thread_id,
        'sender_id': m.sender_id,
        'sender_name': persona.name_by_thread_id(m.thread_id, m.sender),
        'kind': m.kind,
        'body': m.body,
        'url': reverse('chat:file', args=[m.pk]) if m.attachment else '',
        'duration': m.duration or 0,
        'created_at': local.strftime('%d.%m %H:%M'),
        'time': local.strftime('%H:%M'),
        'day': local.date().isoformat(),
        'file_name': meta.get('name', ''),
        'file_size': meta.get('size', 0),
        'w': meta.get('w', 0), 'h': meta.get('h', 0),          # размеры фото: клиент показывает его в своих пропорциях
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
           'circle': _lazy('Видеосообщение'), 'file': _lazy('Файл'), 'poll': _lazy('Опрос')}


def preview(m) -> str:
    """Текст для списка чатов и уведомлений."""
    if m.kind == 'file':
        return m.meta.get('name') or str(PREVIEW['file'])
    from .richtext import plain
    if m.kind in ('photo', 'video') and m.body:              # фото с подписью — показываем подпись
        return plain(m.body)
    return PREVIEW.get(m.kind, '') or plain(m.body)


def notify_recipients(thread, sender, text, silent: bool = False):
    """Колокольчик и пуш получателю (кроме отправителя). «Без звука» — пуш без звука.

    Переписка в базе зашифрована, а таблица уведомлений — нет. Поэтому текст сообщения в неё не кладём:
    в базе остаётся только «Имя: новое сообщение», а сам текст уходит пушем на телефон и нигде не хранится
    (см. quiet_note ниже). Иначе копия базы раскрывала бы начало каждого личного сообщения."""
    from .models import Member

    name = persona.name_in(thread, sender)
    # «без звука» у этого диалога (кнопка «Звук» в профиле собеседника) — уведомление придёт тихо
    muted = set(Member.objects.filter(thread=thread, muted=True).values_list('user_id', flat=True))
    for participant in thread.participants.exclude(pk=sender.pk):
        quiet_note(participant, name, f'/chat/{thread.pk}/', _lazy('новое сообщение'), text,
                   silent=silent or participant.pk in muted)


def quiet_note(user, name: str, url: str, what, text: str, silent: bool = False) -> None:
    """Уведомление о сообщении без его текста в базе: «Имя: новое сообщение». Текст — только в пуше.
    Пока прежнее уведомление об этом чате не прочитано, новую строку не заводим — обновляем её (как счётчик
    непрочитанного в списке чатов), а пуш отправляем всё равно."""
    from django.conf import settings
    from django.db import transaction
    from django.utils import translation

    from apps.core.models import Notification
    uid = user if isinstance(user, int) else user.pk
    lang = '' if isinstance(user, int) else getattr(user, 'language', '')
    with translation.override(lang or settings.LANGUAGE_CODE):
        stored = f'{name}: {what}'
    push = f'{name}: {text[:80]}'
    old = Notification.objects.filter(user_id=uid, url=url, read=False).order_by('-pk').first()
    if old is None:
        note = Notification(user_id=uid, text=stored, url=url, silent=silent)
        note.push_text = push                     # в базу не пишется: apps/api/push.py берёт его для пуша
        note.save()
        return
    Notification.objects.filter(pk=old.pk).update(text=stored, created_at=timezone.now(), silent=silent)
    from apps.api.push import send_to_user
    transaction.on_commit(lambda: send_to_user(uid, push, url, silent=silent))
