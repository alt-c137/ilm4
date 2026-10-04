"""Действия с сообщениями — как в Telegram: ответ, пересылка, правка, закреп, реакции, поиск, «Избранное»,
комментарии к постам канала. Снаружи зовут через services.py.

Правила (сверены с telegram.org/faq и историей обновлений):
* править можно своё сообщение 48 часов (пост канала — без срока); у изменённого видна пометка;
* реакция — одна от человека на сообщение; повторное нажатие снимает её;
* закрепить в личном чате может любой из двоих, в группе и канале — владелец и админы; закрепов может быть много;
* пересылка сохраняет «Переслано от …»; можно скрыть автора; из чата никяха и из «защищённых» чатов пересылать нельзя.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Message, Reaction, Thread

EDIT_HOURS = 48
FORWARD_MAX = 100                  # сообщений за раз
FORWARD_TARGETS = 10               # чатов за раз
SEARCH_SCAN = 3000                 # сколько последних сообщений просматривает поиск по чату
SAVED = 'saved'


def _svc():
    from . import services
    return services


def _error(text, status=400):
    return _svc().ChatError(text, status)


def _get(user, message_id, scheduled: bool = False) -> Message:
    """Сообщение, которое человек видит."""
    s = _svc()
    msg = Message.objects.select_related('thread', 'sender', 'reply_to__sender').filter(pk=message_id).first()
    if msg is None or not s.can_read(msg.thread, user):
        raise _error(_('Сообщение не найдено'), 404)
    if msg.scheduled_at and (not scheduled or msg.sender_id != user.pk):
        raise _error(_('Сообщение не найдено'), 404)
    return msg


# ---------- «Избранное» ----------

def open_saved(user) -> Thread:
    """Чат с самим собой: заметки, пересланное «на потом», файлы — как «Избранное» в Telegram."""
    thread = Thread.objects.filter(kind=Thread.DIRECT, context_type=SAVED, participants=user).first()
    if thread is None:
        thread = Thread.objects.create(subject=str(_('Избранное')), context_type=SAVED)
        thread.participants.add(user)
    return thread


# ---------- правка ----------

def message_raw(user, message_id) -> str:
    """Исходный текст своего сообщения — для правки (в ленте он уже оформлен)."""
    msg = _get(user, message_id, scheduled=True)
    if msg.sender_id != user.pk:
        raise _error(_('Изменить можно только своё сообщение.'), 403)
    return msg.body


def edit_message(user, message_id, body: str) -> dict:
    from .events import message_payload
    s = _svc()
    msg = _get(user, message_id, scheduled=True)
    if msg.sender_id != user.pk or msg.kind in (Message.SYSTEM, Message.POLL):
        raise _error(_('Изменить можно только своё сообщение.'), 403)
    if (not msg.thread.is_channel and not msg.scheduled_at
            and timezone.now() - msg.created_at > timedelta(hours=EDIT_HOURS)):
        raise _error(_('Изменить сообщение можно в течение {v1} часов.').format(v1=EDIT_HOURS))
    body = (body or '').strip()
    if msg.kind == Message.TEXT and not body:
        raise _error(_('Сообщение пустое или слишком длинное'))
    if len(body) > (s.MAX_TEXT if msg.kind == Message.TEXT else 1000):
        raise _error(_('Сообщение пустое или слишком длинное'))
    if msg.kind in (Message.VOICE, Message.CIRCLE):
        raise _error(_('Голосовое и кружок изменить нельзя — удалите и запишите заново.'))
    if s.nikah_contacts_forbidden(msg.thread_id, body):
        raise _error(_('В чате никяха нельзя передавать телефоны, ники и ссылки — общение внутри ilm4, при махраме.'))
    if body == msg.body:
        return message_payload(msg)
    msg.body = body
    fields = ['body']
    if not msg.scheduled_at:
        msg.edited_at = timezone.now()
        fields.append('edited_at')
    msg.save(update_fields=fields)
    payload = message_payload(msg)
    if not msg.scheduled_at:
        s._group_send(msg.thread_id, {'type': 'chat.edited', 'payload': payload})
    return payload


# ---------- закреп ----------

def _can_pin(thread, user) -> bool:
    from . import rooms
    s = _svc()
    if thread.is_room:
        return rooms.is_admin(thread, user)
    return s.is_participant(thread, user)


def pin_message(user, message_id, on: bool = True) -> dict:
    from .events import message_payload
    s = _svc()
    msg = _get(user, message_id)
    if msg.comment_of_id or not _can_pin(msg.thread, user):
        raise _error(_('Закреплять сообщения здесь могут только владелец и админы.'), 403)
    msg.pinned_at = timezone.now() if on else None
    msg.save(update_fields=['pinned_at'])
    payload = message_payload(msg)
    s._group_send(msg.thread_id, {'type': 'chat.pinned', 'id': msg.pk, 'on': bool(on), 'payload': payload})
    return payload


def pinned_messages(thread, user, limit: int = 50) -> list:
    """Закреплённые сообщения чата, от старых к новым."""
    s = _svc()
    rows = list(s.visible_messages(thread, user).filter(pinned_at__isnull=False, scheduled_at__isnull=True)
                .select_related('sender', 'reply_to__sender').order_by('-created_at')[:limit])[::-1]
    for m in rows:
        m.thread = thread
    return rows


# ---------- реакции ----------

def react(user, message_id, emoji: str) -> dict:
    """Поставить реакцию; та же ещё раз — снять; другая — заменить (одна реакция от человека)."""
    from . import rooms
    from .events import reactions_of
    s = _svc()
    msg = _get(user, message_id)
    thread = msg.thread
    emoji = (emoji or '').strip()
    if emoji and emoji not in Reaction.EMOJI:
        raise _error(_('Такой реакции нет.'))
    if not thread.reactions_on:
        raise _error(_('В этом чате реакции выключены.'), 403)
    if thread.is_room and rooms.membership(thread, user) is None:
        raise _error(_('Реакции ставят участники. Вступите — и ставьте.'), 403)
    if not thread.is_room and (not s.is_participant(thread, user) or s.blocked(thread, user)):
        raise _error(_('Нет доступа'), 403)
    mine = Reaction.objects.filter(message=msg, user=user).first()
    now = ''
    if mine is not None and (not emoji or mine.emoji == emoji):
        mine.delete()
    elif emoji:
        Reaction.objects.update_or_create(message=msg, user=user, defaults={'emoji': emoji})
        now = emoji
    rx = reactions_of(msg)
    s._group_send(thread.pk, {'type': 'chat.reaction', 'id': msg.pk, 'reactions': rx, 'user_id': user.pk, 'emoji': now})
    return {'id': msg.pk, 'reactions': rx, 'my_reaction': now}


# ---------- пересылка ----------

class _Plain:
    """Расшифрованный файл как обычный поток (read) — чтобы зашифровать его ключом другого чата."""

    def __init__(self, chunks):
        self._it, self._buf = iter(chunks), b''

    def read(self, n: int = -1) -> bytes:
        while n < 0 or len(self._buf) < n:
            piece = next(self._it, None)
            if piece is None:
                break
            self._buf += piece
        if n < 0:
            out, self._buf = self._buf, b''
        else:
            out, self._buf = self._buf[:n], self._buf[n:]
        return out


def _copy_attachment(src: Message, dst: Message) -> int:
    """Вложение шифруется ключом своего чата — при пересылке перешифровываем ключом чата-получателя."""
    import os
    import uuid

    from . import filecrypt
    name = src.attachment.name
    ext = os.path.splitext(name[:-len(filecrypt.SUFFIX)] if filecrypt.is_sealed(name) else name)[1] or '.bin'
    with src.attachment.open('rb') as fh:
        if filecrypt.is_sealed(name):
            reader = filecrypt.Reader(src.thread_id, fh, src.attachment.size)
            size = reader.size
            stream = _Plain(reader.iter_range(0, max(0, size - 1)))
        else:                                              # старые вложения лежат как есть
            size, stream = src.attachment.size, fh
        dst.attachment.save(uuid.uuid4().hex + ext + filecrypt.SUFFIX, filecrypt.seal_file(dst.thread_id, stream, size),
                            save=False)
    return size


def _origin(msg: Message) -> dict:
    """«Переслано от …»: исходный автор сохраняется при повторной пересылке (как в Telegram)."""
    from apps.accounts import people
    if msg.fwd_enc:
        return msg.fwd
    thread = msg.thread
    if thread.is_channel:                              # пост канала — от имени канала
        return {'name': thread.title, 'user': None, 'room': thread.pk if thread.is_public else None,
                'handle': thread.handle or ''}
    sender = msg.sender
    return {'name': sender.get_display_name(), 'user': sender.pk if people.forward_link(sender) else None, 'room': None}


def forward_messages(user, message_ids, thread_ids, hide_sender: bool = False) -> list:
    """Переслать сообщения в один или несколько чатов. thread_ids может содержать 'saved' — «Избранное»."""
    s = _svc()
    ids = []
    for v in list(message_ids or [])[:FORWARD_MAX]:
        try:
            ids.append(int(v))
        except (TypeError, ValueError):
            continue
    if not ids:
        raise _error(_('Выберите сообщения.'))
    msgs = list(Message.objects.filter(pk__in=ids, scheduled_at__isnull=True).exclude(kind=Message.SYSTEM)
                .select_related('thread', 'sender').order_by('created_at', 'pk'))
    if not msgs:
        raise _error(_('Сообщение не найдено'), 404)
    for m in msgs:
        if not s.visible_messages(m.thread, user).filter(pk=m.pk).exists() or not s.can_read(m.thread, user):
            raise _error(_('Сообщение не найдено'), 404)
        if m.thread.protected or s.is_nikah(m.thread_id):
            raise _error(_('Из этого чата пересылать нельзя.'), 403)
    targets = []
    for v in list(thread_ids or [])[:FORWARD_TARGETS]:
        if str(v) == SAVED:
            targets.append(open_saved(user))
            continue
        try:
            t = Thread.objects.filter(pk=int(v)).first()
        except (TypeError, ValueError):
            t = None
        if t is not None and t not in targets:
            targets.append(t)
    if not targets:
        raise _error(_('Выберите, куда переслать.'))
    out = []
    for target in targets:
        s._check_can_write(target, user)
        flags = s.flags(target)
        for m in msgs:
            if m.kind != Message.TEXT and m.kind != Message.POLL and not flags.get(m.kind):
                raise _error(_('В этом чате такие вложения отключены.'), 403)
            if m.kind == Message.POLL:
                continue                                  # опрос привязан к своему чату — не пересылаем
            if s.nikah_contacts_forbidden(target.pk, m.body):
                raise _error(_('В чате никяха нельзя передавать телефоны, ники и ссылки — общение внутри ilm4, при махраме.'))
            with transaction.atomic():
                copy = Message(thread=target, sender=user, kind=m.kind, duration=m.duration, body=m.body)
                if not hide_sender and not (m.sender_id == user.pk and not m.fwd_enc and not m.thread.is_channel):
                    copy.set_fwd(**_origin(m))            # своё собственное сообщение пересылается без «от кого»
                if m.attachment:
                    size = m.attachment.size
                    s._check_room(user, size)
                    plain = _copy_attachment(m, copy)
                    s._count_upload(user, plain)
                    if m.kind == Message.FILE:
                        copy.set_meta(**{**m.meta, 'size': plain})
                    elif m.meta_enc:                      # размеры фото переезжают вместе с ним
                        copy.set_meta(**m.meta)
                copy.save()
            s._touch(target, user)
            out.append(s._broadcast(copy))
    return out


# ---------- поиск и «окно» вокруг сообщения ----------

def search_messages(thread, user, q: str, limit: int = 50) -> list:
    """Поиск по тексту в чате. Сообщения в базе зашифрованы, поэтому ищем среди последних расшифрованных
    (до SEARCH_SCAN штук) — этого хватает для обычной переписки."""
    s = _svc()
    q = (q or '').strip().casefold()[:80]
    if len(q) < 2 or not s.search_allowed(user):
        return []
    found = []
    qs = (s.visible_messages(thread, user).filter(scheduled_at__isnull=True).exclude(body_enc='')
          .select_related('sender').order_by('-created_at', '-pk')[:SEARCH_SCAN])
    for m in qs.iterator(chunk_size=300):
        m.thread = thread
        if q in m.body.casefold():
            found.append(m)
            if len(found) >= limit:
                break
    return found


def window_around(thread, user, message_id, half: int = 40) -> dict:
    """Сообщения вокруг заданного (переход к ответу, закрепу, найденному): half до и half после."""
    s = _svc()
    base = s.visible_messages(thread, user).select_related('sender', 'reply_to__sender')
    target = base.filter(pk=message_id).first()
    if target is None:
        raise _error(_('Сообщение не найдено'), 404)
    before = list(base.filter(created_at__lte=target.created_at).exclude(pk=target.pk)
                  .order_by('-created_at', '-pk')[:half + 1])
    after = list(base.filter(created_at__gt=target.created_at).order_by('created_at', 'pk')[:half + 1])
    rows = before[:half][::-1] + [target] + after[:half]
    for m in rows:
        m.thread = thread
    return {'items': rows, 'more_before': len(before) > half, 'more_after': len(after) > half}


# ---------- комментарии к постам канала ----------

def _post(user, post_id) -> Message:
    post = _get(user, post_id)
    if not post.thread.is_channel or post.comment_of_id or not post.thread.comments_on:
        raise _error(_('У этого поста нет комментариев.'), 404)
    return post


def comments_of(user, post_id, limit: int = 200) -> dict:
    post = _post(user, post_id)
    rows = list(Message.objects.filter(comment_of=post).exclude(hidden_for__user=user)
                .select_related('sender', 'reply_to__sender').order_by('created_at', 'pk')[:limit])
    for m in [post, *rows]:
        m.thread = post.thread
    return {'post': post, 'items': rows}


def add_comment(user, post_id, body: str, reply_to=None) -> dict:
    """Комментарий под постом канала — пишут подписчики (сам канал по-прежнему ведут только админы)."""
    from . import rooms
    s = _svc()
    post = _post(user, post_id)
    thread = post.thread
    m = rooms.membership(thread, user)
    if thread.closed or m is None:
        raise _error(_('Комментировать могут подписчики канала.'), 403)
    body = (body or '').strip()
    if not body or len(body) > s.MAX_TEXT:
        raise _error(_('Сообщение пустое или слишком длинное'))
    target = None
    if reply_to:
        target = Message.objects.filter(pk=reply_to, comment_of=post).select_related('sender').first()
    with transaction.atomic():
        msg = Message.objects.create(thread=thread, sender=user, body=body, comment_of=post, reply_to=target)
        Message.objects.filter(pk=post.pk).update(comments_count=F('comments_count') + 1)
    payload = s._broadcast(msg)
    if target is not None and target.sender_id != user.pk:      # ответили на мой комментарий — уведомить
        from django.utils.translation import gettext_lazy as _lazy

        from .events import quiet_note
        quiet_note(target.sender, user.get_display_name(), f'/chat/{thread.pk}/post/{post.pk}/',
                   _lazy('ответ на ваш комментарий'), body)
    return payload


__all__ = ['add_comment', 'comments_of', 'edit_message', 'forward_messages', 'message_raw', 'open_saved', 'pin_message',
           'pinned_messages', 'react', 'search_messages', 'window_around']
