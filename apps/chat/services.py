"""Мессенджер: единственная точка входа для остального кода (docs/MESSENGER.md §1).

Сайт (views.py), WebSocket (consumers.py), API приложения (apps/api/views_chat.py)
и другие разделы (никях, объявления, сделки) вызывают только эти функции. Когда
мессенджер станет отдельным сервисом, эти функции превратятся в вызовы его API
с теми же аргументами — остальной код менять не придётся.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Message, Thread

MAX_TEXT = 2000
MAX_SCHEDULE_DAYS = 365


class ChatError(Exception):
    """Отказ с понятным текстом для человека и HTTP-статусом."""

    def __init__(self, message, status=400):
        super().__init__(str(message))
        self.message, self.status = str(message), status


UploadRefused = ChatError       # старое имя (сайт и API ловили его)


# ---------- диалоги ----------

def open_direct(user, other, subject: str = '', context=None) -> Thread:
    """Диалог двоих (найти или создать).

    context=('buy', 12) — чат по объявлению №12: у каждого объявления свой чат (как на Avito),
    сверху карточка объявления. Без контекста — обычный личный чат этих двоих.
    Контекст принимается, только если объект принадлежит собеседнику (contexts.resolve).
    """
    from apps.accounts.models import UserBlock

    from . import contexts
    if UserBlock.between(user, other):
        raise ChatError(_('Переписка недоступна: один из вас заблокировал другого.'), 403)
    found = contexts.resolve(context[0], context[1], other) if context else None
    ctx_type, ctx_id = (found[0].key, found[1].pk) if found else ('', None)
    if found:
        subject = found[0].title_of(found[1])
    subject = (subject or '').strip()[:160]
    thread = (Thread.objects.filter(kind=Thread.DIRECT, participants=user, context_type=ctx_type, context_id=ctx_id)
              .filter(participants=other).first())
    if thread is None:
        thread = Thread.objects.create(subject=subject, context_type=ctx_type, context_id=ctx_id)
        thread.participants.add(user, other)
    elif subject and thread.subject != subject:
        thread.subject = subject                      # название объявления изменилось / другая тема разговора
        thread.save(update_fields=['subject', 'updated_at'])
    return thread


def open_private_thread(users, observers=(), subject: str = '', context=None) -> Thread:
    """Диалог для раздела (пара никяха + свидетели-махрамы)."""
    ctx_type, ctx_id = context or ('', None)
    thread = Thread.objects.create(subject=subject[:160], context_type=ctx_type, context_id=ctx_id)
    thread.participants.add(*users, *observers)
    if observers:
        thread.observers.add(*observers)
    return thread


def support_user():
    from apps.core.models import SiteSettings
    u = SiteSettings.get_solo().support_user
    return u if u and u.is_active else None


def open_support(user) -> Thread:
    """Чат с командой ilm4 (аккаунт поддержки задаётся в «Настройках сайта»)."""
    from . import contexts
    staff = support_user()
    if staff is None or staff.pk == user.pk:
        raise ChatError(_('Чат поддержки сейчас недоступен — напишите на странице «Поддержка».'), 404)
    thread = (Thread.objects.filter(context_type=contexts.SUPPORT, participants=user).filter(participants=staff).first())
    if thread is None:
        thread = Thread.objects.create(subject=str(_('Поддержка ilm4')), context_type=contexts.SUPPORT)
        thread.participants.add(user, staff)
    return thread


def thread_info(thread, user) -> dict:
    """Всё о типе чата для клиента: папка, карточка объявления, подсказка раздела."""
    from . import contexts
    return {'folder': thread.folder, 'context': thread.context_type, 'card': contexts.card(thread, user),
            'notice': contexts.notice(thread), 'warn_text': contexts.warn_text() if contexts.risky(thread) else ''}


def folders_for(user, rows) -> list:
    """Папки для списка чатов: только те, где есть диалоги, с числом непрочитанных."""
    seen = {}
    for r in rows:
        f = seen.setdefault(r['folder'], {'n': 0, 'unread': 0})
        f['n'] += 1
        f['unread'] += r['unread']
    return [{'key': k, 'name': str(label), **seen[k]} for k, label in Thread.FOLDERS if k in seen]


def is_participant(thread, user) -> bool:
    return thread.participants.filter(pk=user.pk).exists()


def blocked(thread, user) -> bool:
    """Кто-то из участников заблокировал другого — писать нельзя."""
    from apps.accounts.models import UserBlock
    return any(UserBlock.between(user, p) for p in thread.participants.exclude(pk=user.pk))


def is_nikah(thread_id) -> bool:
    from apps.nikah.models import NikahMatch
    return NikahMatch.objects.filter(thread_id=thread_id).exists()


def allowed_file_mb() -> int:
    from apps.core.models import SiteSettings
    return SiteSettings.get_solo().chat_file_max_mb


def nikah_contacts_forbidden(thread_id, body: str) -> bool:
    """Чат никяха: телефоны, ники и ссылки не пропускаем (настройка в админке)."""
    from apps.core.models import SiteSettings
    if not SiteSettings.get_solo().nikah_chat_block_contacts:
        return False
    from apps.nikah.services import has_contacts
    return has_contacts(body) and is_nikah(thread_id)


def flags(thread=None) -> dict:
    """Что разрешено в чате (выключатели в админке). Для пары никяха фото/видео/кружки —
    отдельным выключателем: иначе фото ушли бы в обход защищённого обмена."""
    from apps.core.models import SiteSettings
    st = SiteSettings.get_solo()
    media = True
    if thread is not None and not st.nikah_chat_media:
        media = not is_nikah(thread.pk)
    return {'contacts': st.chat_contacts_enabled, 'photo': st.chat_photos_enabled and media,
            'video': st.chat_videos_enabled and media, 'voice': st.chat_voice_enabled,
            'circle': st.chat_circles_enabled and media,
            'file': st.chat_files_enabled and media, 'file_max_mb': st.chat_file_max_mb,
            'support': bool(st.support_user_id),
            'calls': st.chat_calls_enabled, 'video_calls': st.chat_video_calls_enabled,
            'schedule': True, 'silent': True,
            'turn': {'url': st.webrtc_turn_url, 'username': st.webrtc_turn_username,
                     'credential': st.webrtc_turn_credential} if st.webrtc_turn_url else None}


def visible_messages(thread, user):
    """Сообщения диалога, которые видит человек (чужие запланированные — нет)."""
    return thread.messages.visible_to(user)


def mark_read(thread, user) -> int:
    return (thread.messages.delivered().filter(read_at__isnull=True).exclude(sender=user)
            .update(read_at=timezone.now()))


# ---------- отправка ----------

def _check_can_write(thread, user):
    if not is_participant(thread, user):
        raise ChatError(_('Нет доступа'), 403)
    if blocked(thread, user):
        raise ChatError(_('Переписка недоступна: блокировка'), 403)


def parse_schedule(value):
    """Время «отправить в …» из ISO-строки. Прошлое и «через секунду» — отправить сразу."""
    if not value:
        return None
    from django.utils.dateparse import parse_datetime
    when = parse_datetime(str(value)) if not hasattr(value, 'tzinfo') else value
    if when is None:
        raise ChatError(_('Не понял время отправки'))
    if timezone.is_naive(when):
        when = timezone.make_aware(when)
    now = timezone.now()
    if when <= now + timedelta(seconds=30):
        return None
    if when > now + timedelta(days=MAX_SCHEDULE_DAYS):
        raise ChatError(_('Запланировать можно не дальше чем на год вперёд'))
    return when


def _broadcast(msg) -> dict:
    """Разослать участникам по WebSocket и уведомить (с учётом «без звука»)."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from .events import message_payload, notify_recipients, preview
    payload = message_payload(msg)
    layer = get_channel_layer()
    if layer is not None:
        async_to_sync(layer.group_send)(f'chat_{msg.thread_id}', {'type': 'chat.message', 'payload': payload})
    if msg.kind != Message.SYSTEM:
        notify_recipients(msg.thread, msg.sender, str(preview(msg)), silent=msg.silent)
    return payload


def send_text(thread, user, body: str, silent: bool = False, schedule=None, broadcast: bool = True) -> dict:
    """Текстовое сообщение (сайт, приложение, WebSocket — одни и те же проверки)."""
    from .events import message_payload
    body = (body or '').strip()
    if not body or len(body) > MAX_TEXT:
        raise ChatError(_('Сообщение пустое или слишком длинное'))
    _check_can_write(thread, user)
    if nikah_contacts_forbidden(thread.pk, body):
        raise ChatError(_('В чате никяха нельзя передавать телефоны, ники и ссылки — общение внутри ilm4, при махраме.'))
    when = parse_schedule(schedule)
    msg = Message.objects.create(thread=thread, sender=user, body=body, silent=bool(silent), scheduled_at=when)
    if when:
        return message_payload(msg)          # видно только автору, уйдёт в своё время
    thread.save(update_fields=['updated_at'])
    return _broadcast(msg) if broadcast else message_payload(msg)


def store_upload(thread, user, kind, upload_file, duration=None, caption='', silent=False, schedule=None) -> dict:
    """Фото / видео / голосовое / кружок / файл: проверить, зашифровать, сохранить, разослать.

    kind='file' — «отправить файлом»: любой документ, а также фото и видео без сжатия.
    kind='video' — сервер потом пережмёт до качества из настроек (transcode.py), как делает Telegram.
    """
    from .events import message_payload
    from .filecrypt import SUFFIX, seal_file
    from .media import MediaError, clean_name, prepare

    _check_can_write(thread, user)
    if kind not in ('photo', 'video', 'voice', 'circle', 'file') or not flags(thread).get(kind):
        raise ChatError(_('Эта функция сейчас отключена'), 403)
    if not upload_file:
        raise ChatError(_('Файл не получен'))
    original = clean_name(getattr(upload_file, 'name', ''))
    try:
        content, sec = prepare(kind, upload_file, duration)
    except MediaError as exc:
        raise ChatError(str(exc)) from exc
    when = parse_schedule(schedule)
    size = content.size
    msg = Message(thread=thread, sender=user, kind=kind, duration=sec, body=(caption or '').strip()[:1000],
                  silent=bool(silent), scheduled_at=when)
    if kind == 'file':
        msg.set_meta(name=original, size=size)
    msg.attachment.save(content.name + SUFFIX, seal_file(thread.pk, content, size), save=False)
    msg.save()
    if kind == 'video':
        from . import transcode
        transcode.schedule(msg.pk)
    if when:
        return message_payload(msg)
    thread.save(update_fields=['updated_at'])
    return _broadcast(msg)


def system_message(thread, sender, text: str, duration=None, broadcast: bool = False) -> dict:
    """Служебная запись в переписке (открыт чат никяха, звонок 3:12, пропущенный)."""
    msg = Message.objects.create(thread=thread, sender=sender, kind=Message.SYSTEM, body=text, duration=duration)
    thread.save(update_fields=['updated_at'])
    if broadcast:
        return _broadcast(msg)
    from .events import message_payload
    return message_payload(msg)


def cancel_scheduled(user, message_id) -> None:
    msg = Message.objects.filter(pk=message_id, sender=user, scheduled_at__isnull=False).first()
    if msg is None:
        raise ChatError(_('Запланированное сообщение не найдено'), 404)
    if msg.attachment:
        msg.attachment.delete(save=False)
    msg.delete()


def send_scheduled_now(user, message_id) -> dict:
    with transaction.atomic():
        msg = (Message.objects.select_for_update().filter(pk=message_id, sender=user, scheduled_at__isnull=False)
               .first())
        if msg is None:
            raise ChatError(_('Запланированное сообщение не найдено'), 404)
        _deliver(msg)
    return _broadcast(msg)


def _deliver(msg) -> None:
    msg.scheduled_at = None
    msg.created_at = timezone.now()           # время в переписке — когда ушло, как в Telegram
    msg.save(update_fields=['scheduled_at', 'created_at'])
    Thread.objects.filter(pk=msg.thread_id).update(updated_at=timezone.now())


def deliver_due(now=None) -> int:
    """Отправить запланированные, чьё время пришло (manage.py chat_send_due, раз в минуту)."""
    now = now or timezone.now()
    sent = 0
    for pk in list(Message.objects.filter(scheduled_at__lte=now).values_list('pk', flat=True)[:500]):
        with transaction.atomic():
            msg = Message.objects.select_for_update().filter(pk=pk, scheduled_at__isnull=False).first()
            if msg is None:
                continue                       # уже отправлено вручную или удалено
            if blocked(msg.thread, msg.sender) or not msg.sender.is_active:
                msg.delete()                   # за это время появилась блокировка — не доставляем
                continue
            _deliver(msg)
        _broadcast(msg)
        sent += 1
    return sent
