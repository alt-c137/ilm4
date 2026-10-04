"""Мессенджер: единственная точка входа для остального кода (docs/MESSENGER.md §1).

Сайт (views.py), WebSocket (consumers.py), API приложения (apps/api/views_chat.py)
и другие разделы (никях, объявления, сделки) вызывают только эти функции. Когда
мессенджер станет отдельным сервисом, эти функции превратятся в вызовы его API
с теми же аргументами — остальной код менять не придётся.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Message, Thread

MAX_TEXT = 2000
MAX_SCHEDULE_DAYS = 365
MB = 1024 * 1024
PART = 4 * MB                   # размер части при загрузке большого файла (кратен куску шифрования)
PART_MAX = 8 * MB
UPLOAD_TTL_HOURS = 24           # недокачанный файл живёт сутки — потом удаляется


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
    """Всё о типе чата для клиента: папка, карточка объявления, подсказка раздела, группа / канал."""
    from . import contexts, rooms
    return {'folder': thread.folder, 'context': thread.context_type, 'card': contexts.card(thread, user),
            'notice': contexts.notice(thread), 'warn_text': contexts.warn_text() if contexts.risky(thread) else '',
            'room': rooms.info(thread, user) if thread.is_room else None,
            'support': support_state(thread, user)}       # 'call' — можно позвать поддержку третьей, 'drop' — она уже в чате


def inbox(user, limit: int = 300, space=None) -> list:
    """Диалоги человека для списка чатов — фиксированным числом запросов, сколько бы чатов ни было.

    Возвращает [(thread, other, last)]: собеседник (не свидетель; у группы и канала — None)
    и последнее видимое сообщение. У thread есть .unread: в личном чате — по Message.read_at,
    в группе и канале — всё, что новее Member.last_read_at. И личное состояние (как в Telegram):
    .pinned_at, .archived, .unread_mark, .draft. Закреплённые идут первыми.
    Каналы сообществ в общий список не попадают; space=сообщество — наоборот, только его каналы."""
    from django.db.models import Count, Exists, OuterRef, Q, Subquery

    from . import rooms
    from .models import ChatState, HiddenMessage, Member
    visible = (Message.objects.filter(thread=OuterRef('pk'), comment_of__isnull=True)
               .filter(Q(scheduled_at__isnull=True) | Q(sender=user))
               .exclude(Exists(HiddenMessage.objects.filter(message=OuterRef('pk'), user=user))))
    mine = Member.objects.filter(thread=OuterRef('pk'), user=user)
    incoming = Q(messages__scheduled_at__isnull=True, messages__comment_of__isnull=True) & ~Q(messages__sender=user)
    threads = list(
        user.chat_threads.filter(kind__in=rooms.visible_kinds(), **({'space': space} if space is not None else {'space__isnull': True}))
        .prefetch_related('participants', 'observers')
        .annotate(read_until=Subquery(mine.values('last_read_at')[:1]), muted=Subquery(mine.values('muted')[:1]),
                  last_id=Subquery(visible.order_by('-created_at', '-pk').values('pk')[:1]))
        .annotate(unread_direct=Count('messages', filter=incoming & Q(messages__read_at__isnull=True)),
                  unread_room=Count('messages', filter=incoming & ~Q(messages__kind=Message.SYSTEM)
                                    & (Q(read_until__isnull=True) | Q(messages__created_at__gt=F('read_until')))))[:limit])
    states = {st.thread_id: st for st in ChatState.objects.filter(user=user, thread__in=[t.pk for t in threads])}
    threads = [t for t in threads if not (states.get(t.pk) and states[t.pk].hidden)]
    for t in threads:                             # очищенная история: считаем заново только то, что после очистки
        st = states.get(t.pk)
        if st is not None and st.cleared_at:
            after = visible_messages(t, user).filter(created_at__gt=st.cleared_at)
            t.last_id = after.order_by('-created_at', '-pk').values_list('pk', flat=True).first()
            fresh = after.exclude(sender=user).exclude(kind=Message.SYSTEM)
            t.unread_room = fresh.filter(created_at__gt=t.read_until).count() if t.read_until else fresh.count()
            t.unread_direct = fresh.filter(read_at__isnull=True).count()
    last = Message.objects.select_related('sender').in_bulk([t.last_id for t in threads if t.last_id])
    rows = []
    for t in threads:
        st = states.get(t.pk)
        t.unread = t.unread_room if t.is_room else t.unread_direct
        if t.is_saved:
            t.unread = 0
        t.pinned_at = st.pinned_at if st else None
        t.archived = bool(st and st.archived)
        t.unread_mark = bool(st and st.unread_mark)
        t.draft = _draft_text(t.pk, st)
        other = None
        if not t.is_room and not t.is_saved:
            watchers = {u.pk for u in t.observers.all()}
            others = [u for u in t.participants.all() if u.pk != user.pk]
            other = next((u for u in others if u.pk not in watchers), None) or (others[0] if others else None)
        msg = last.get(t.last_id)
        if msg is not None:
            msg.thread = t                       # для расшифровки и превью — без запроса за чатом
        rows.append((t, other, msg))
    # закреплённые — сверху (позже закрепил — выше), остальные — по времени последнего сообщения
    rows.sort(key=lambda r: (r[0].pinned_at is None, -(r[0].pinned_at.timestamp()) if r[0].pinned_at else 0))
    return rows


def _draft_text(thread_id, state) -> str:
    if state is None or not state.draft_enc:
        return ''
    from .keyring import decrypt_text
    try:
        return decrypt_text(thread_id, state.draft_enc)
    except ValueError:
        return ''


def folders_for(user, rows) -> list:
    """Папки для списка чатов: только те, где есть диалоги, с числом непрочитанных."""
    seen = {}
    for r in rows:
        f = seen.setdefault(r['folder'], {'n': 0, 'unread': 0})
        f['n'] += 1
        f['unread'] += r['unread']
    return [{'key': k, 'name': str(label), **seen[k]} for k, label in Thread.FOLDERS if k in seen]


def set_muted(thread, user, muted: bool) -> None:
    """«Без звука» для этого человека: у группы и канала — в его участии, у личного диалога — отдельной отметкой."""
    from . import rooms
    from .models import Member
    if thread.is_room:
        return rooms.set_muted(thread, user, muted)
    if not is_participant(thread, user):
        raise ChatError(_('Нет доступа'), 403)
    Member.objects.update_or_create(thread=thread, user=user, defaults={'muted': bool(muted)})


def is_muted(thread, user) -> bool:
    from .models import Member
    return Member.objects.filter(thread=thread, user=user, muted=True).exists()


def shared_media(thread, user, what: str = 'media', limit: int = 60, before: int = 0):
    """Вложения чата для вкладок профиля: media — фото и видео, files — файлы, voice — голосовые и кружки."""
    kinds = {'media': (Message.PHOTO, Message.VIDEO), 'files': (Message.FILE,),
             'voice': (Message.VOICE, Message.CIRCLE)}.get(what)
    if kinds is None or not can_read(thread, user):
        raise ChatError(_('Нет доступа'), 403)
    qs = thread.messages.delivered().filter(kind__in=kinds).select_related('sender').order_by('-pk')
    if before:
        qs = qs.filter(pk__lt=before)
    rows = list(qs[:limit])
    for m in rows:
        m.thread = thread
    return rows


def direct_between(user, other):
    """Обычный личный диалог двоих (без привязки к объявлению), если он уже есть."""
    return (Thread.objects.filter(kind=Thread.DIRECT, participants=user, context_type='', context_id__isnull=True)
            .filter(participants=other).first())


def is_participant(thread, user) -> bool:
    return thread.participants.filter(pk=user.pk).exists()


def can_read(thread, user) -> bool:
    """Кому можно открыть чат: участникам; публичную группу или канал — любому вошедшему."""
    from . import rooms
    return rooms.can_read(thread, user)


def blocked(thread, user) -> bool:
    """Кто-то из участников заблокировал другого — писать нельзя (только личные диалоги)."""
    from apps.accounts.models import UserBlock
    if thread.is_room:
        return False
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
    # звонки — только в личных диалогах с другим человеком: в «Избранном» (чат с самим собой) звонить некому
    direct = thread is None or (not thread.is_room and not thread.is_saved)
    return {'contacts': st.chat_contacts_enabled, 'photo': st.chat_photos_enabled and media,
            'video': st.chat_videos_enabled and media, 'voice': st.chat_voice_enabled,
            'circle': st.chat_circles_enabled and media,
            'file': st.chat_files_enabled and media, 'file_max_mb': st.chat_file_max_mb,
            'video_height': st.chat_video_height,
            'support': bool(st.support_user_id),
            'calls': st.chat_calls_enabled and direct, 'video_calls': st.chat_video_calls_enabled and direct,
            'groups': st.chat_groups_enabled, 'channels': st.chat_channels_enabled,
            'schedule': True, 'silent': True,
            'turn': {'url': st.webrtc_turn_url, 'username': st.webrtc_turn_username,
                     'credential': st.webrtc_turn_credential} if st.webrtc_turn_url else None}


def visible_messages(thread, user):
    """Сообщения диалога, которые видит человек: без чужих запланированных, без удалённых «у себя»,
    без комментариев к постам и без того, что было до «очистить историю»."""
    from .models import ChatState
    qs = thread.messages.visible_to(user)
    cleared = (ChatState.objects.filter(thread=thread, user=user, cleared_at__isnull=False)
               .values_list('cleared_at', flat=True).first()) if getattr(user, 'pk', None) else None
    return qs.filter(created_at__gt=cleared) if cleared else qs


def unread_total(user) -> int:
    """Сколько непрочитанного во всех чатах — для значка в меню. Считается не чаще раза в 20 секунд на человека."""
    from django.core.cache import cache
    key = f'chat:unread:{user.pk}'
    n = cache.get(key)
    if n is None:
        n = sum(t.unread for t, _o, _m in inbox(user) if not getattr(t, 'archived', False) and not getattr(t, 'muted', False))
        cache.set(key, n, 20)
    return n


def mark_read(thread, user) -> int:
    from django.core.cache import cache

    from .models import ChatState
    cache.delete(f'chat:unread:{user.pk}')
    ChatState.objects.filter(thread=thread, user=user, unread_mark=True).update(unread_mark=False)
    if thread.is_room:
        from . import rooms
        rooms.mark_read(thread, user)
        return 0
    return (thread.messages.delivered().filter(read_at__isnull=True).exclude(sender=user)
            .update(read_at=timezone.now()))


# ---------- отправка ----------

def _check_can_write(thread, user):
    if thread.is_room:
        from . import rooms
        rooms.check_post(thread, user)
        if thread.space_id:                                # канал сообщества: тайм-аут участника
            from . import spaces
            spaces.check_write(thread, user)
        if thread.slow_seconds and thread.kind == Thread.GROUP and not rooms.is_admin(thread, user):
            last = (thread.messages.filter(sender=user, scheduled_at__isnull=True).order_by('-created_at')
                    .values_list('created_at', flat=True).first())
            if last and (timezone.now() - last).total_seconds() < thread.slow_seconds:
                wait = int(thread.slow_seconds - (timezone.now() - last).total_seconds()) + 1
                raise ChatError(_('Медленный режим: следующее сообщение — через {v1} с.').format(v1=wait), 429)
        return
    if thread.is_saved:
        if not is_participant(thread, user):
            raise ChatError(_('Нет доступа'), 403)
        return
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

    from .events import message_payload, preview
    payload = message_payload(msg)
    layer = get_channel_layer()
    if layer is not None:
        async_to_sync(layer.group_send)(f'chat_{msg.thread_id}', {'type': 'chat.message', 'payload': payload})
    if msg.kind != Message.SYSTEM and not msg.comment_of_id:
        notify(msg.thread, msg.sender, str(preview(msg)), silent=msg.silent, msg=msg)
    return payload


def notify(thread, sender, text: str, silent: bool = False, msg=None) -> None:
    """Сообщить получателям: в личном диалоге — колокольчик и пуш, в группе и канале — только пуш.
    Упомянутым (@имя) и автору сообщения, на которое ответили, пуш придёт даже при «без звука» — как в Telegram."""
    if thread.is_saved:
        return None
    if thread.is_room:
        from . import rooms
        return rooms.notify(thread, sender, text, silent=silent, always=_must_notify(thread, msg))
    from .events import notify_recipients
    notify_recipients(thread, sender, text, silent=silent)


def _must_notify(thread, msg) -> set:
    """Кого уведомить в группе даже при «без звука»: упомянутых и того, кому ответили."""
    import re
    if msg is None:
        return set()
    ids = set()
    if msg.reply_to_id and msg.reply_to and msg.reply_to.sender_id != msg.sender_id:
        ids.add(msg.reply_to.sender_id)
    handles = set(re.findall(r'(?<![\w@])@([a-z][a-z0-9_]{3,31})', (msg.body or '').lower()))
    if handles:
        ids.update(thread.participants.filter(handle__in=handles).values_list('pk', flat=True))
    if thread.space_id:                                    # канал сообщества: @everyone и @роль
        from . import spaces
        ids.update(spaces.mention_targets(thread, msg.sender, msg.body))
    ids.discard(msg.sender_id)
    return ids


def _touch(thread, sender) -> None:
    """Новое сообщение в чате: поднять чат в списке; у получателей вернуть его из архива (если не «без звука»)
    и из «удалённых у себя» — как в Telegram."""
    from .models import ChatState, Member
    thread.save(update_fields=['updated_at'])
    states = ChatState.objects.filter(thread=thread)
    states.filter(user=sender).exclude(draft_enc='').update(draft_enc='')      # отправил — черновика больше нет
    states.filter(hidden=True).update(hidden=False)
    muted = Member.objects.filter(thread=thread, muted=True).values('user_id')
    states.filter(archived=True).exclude(user=sender).exclude(user__in=muted).update(archived=False)


def reply_target(thread, user, reply_to):
    """Сообщение, на которое отвечают: из этого же чата и видимое человеку. Иначе — без ответа."""
    if not reply_to:
        return None
    try:
        pk = int(reply_to)
    except (TypeError, ValueError):
        return None
    return visible_messages(thread, user).filter(pk=pk, scheduled_at__isnull=True).select_related('sender').first()


def send_text(thread, user, body: str, silent: bool = False, schedule=None, broadcast: bool = True,
              reply_to=None) -> dict:
    """Текстовое сообщение (сайт, приложение, WebSocket — одни и те же проверки)."""
    from .events import message_payload
    body = (body or '').strip()
    if not body or len(body) > MAX_TEXT:
        raise ChatError(_('Сообщение пустое или слишком длинное'))
    _check_can_write(thread, user)
    if nikah_contacts_forbidden(thread.pk, body):
        raise ChatError(_('В чате никяха нельзя передавать телефоны, ники и ссылки — общение внутри ilm4, при махраме.'))
    when = parse_schedule(schedule)
    msg = Message.objects.create(thread=thread, sender=user, body=body, silent=bool(silent), scheduled_at=when,
                                 reply_to=reply_target(thread, user, reply_to))
    if when:
        return message_payload(msg)          # видно только автору, уйдёт в своё время
    _touch(thread, user)
    return _broadcast(msg) if broadcast else message_payload(msg)


def store_upload(thread, user, kind, upload_file, duration=None, caption='', silent=False, schedule=None,
                 reply_to=None) -> dict:
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
    _check_room(user, upload_file.size)
    original = clean_name(getattr(upload_file, 'name', ''))
    try:
        content, sec = prepare(kind, upload_file, duration)
    except MediaError as exc:
        raise ChatError(str(exc)) from exc
    when = parse_schedule(schedule)
    size = content.size
    msg = Message(thread=thread, sender=user, kind=kind, duration=sec, body=(caption or '').strip()[:1000],
                  silent=bool(silent), scheduled_at=when, reply_to=reply_target(thread, user, reply_to))
    if kind == 'file':
        msg.set_meta(name=original, size=size)
    elif getattr(content, 'dims', None):
        msg.set_meta(w=content.dims[0], h=content.dims[1])
    msg.attachment.save(content.name + SUFFIX, seal_file(thread.pk, content, size), save=False)
    msg.save()
    _count_upload(user, size)
    if kind == 'video':
        from . import transcode
        transcode.schedule(msg.pk)
    if when:
        return message_payload(msg)
    _touch(thread, user)
    return _broadcast(msg)


# ---------- большие файлы: загрузка частями ----------

def _quota_key(user) -> str:
    return f'chat:uploaded:{user.pk}:{timezone.localdate().isoformat()}'


def _check_room(user, size: int) -> None:
    """Место на диске и дневной лимит человека: один аккаунт не должен забить сервер файлами."""
    import shutil

    from django.conf import settings
    from django.core.cache import cache

    from apps.core.models import SiteSettings
    daily = SiteSettings.get_solo().chat_daily_upload_mb * MB
    if daily and cache.get(_quota_key(user), 0) + size > daily:
        raise ChatError(_('Дневной лимит загрузки исчерпан ({v1} МБ в сутки). Попробуйте завтра.')
                        .format(v1=daily // MB), 429)
    reserve = getattr(settings, 'CHAT_DISK_RESERVE_MB', 1024) * MB
    try:
        free = shutil.disk_usage(settings.MEDIA_ROOT).free
    except OSError:
        return
    if free - size < reserve:
        raise ChatError(_('На сервере заканчивается место — файл пока не принять. Мы уже знаем об этом.'), 507)


def _count_upload(user, size: int) -> None:
    from django.core.cache import cache
    key = _quota_key(user)
    cache.set(key, cache.get(key, 0) + size, 26 * 3600)


def _upload_path(name: str) -> str:
    import os

    from django.conf import settings
    return os.path.join(settings.MEDIA_ROOT, name)


def upload_begin(thread, user, kind, name, size, duration=None, caption='', silent=False, schedule=None,
                 reply_to=None) -> dict:
    """Начать загрузку большого файла или видео частями. Возвращает id загрузки и размер части.

    Дальше клиент шлёт части по порядку (upload_part) и завершает (upload_finish). Оборвалась
    связь — спрашивает upload_status и продолжает с того же места."""
    import json
    import os
    import uuid

    from . import filecrypt
    from .keyring import encrypt_text
    from .media import LIMITS, clean_name
    from .models import Upload

    _check_can_write(thread, user)
    if kind not in ('file', 'video') or not flags(thread).get(kind):
        raise ChatError(_('Эта функция сейчас отключена'), 403)
    try:
        size = int(size)
    except (TypeError, ValueError):
        raise ChatError(_('Файл не получен')) from None
    if size <= 0:
        raise ChatError(_('Файл пустой'))
    limit = allowed_file_mb() * MB
    if size > limit:
        raise ChatError(_('Файл больше {v1} МБ').format(v1=limit // MB))
    _check_room(user, size)
    parse_schedule(schedule)                                        # кривое время — отказать сразу, а не в конце
    if Upload.objects.filter(user=user).count() >= 5:
        raise ChatError(_('Сначала дождитесь, пока загрузятся предыдущие файлы.'), 429)
    try:
        sec = max(0, min(int(float(duration or 0)), LIMITS['video'][1])) if kind == 'video' else None
    except (TypeError, ValueError):
        sec = 0
    rel = f'chat/tmp/{uuid.uuid4().hex}{filecrypt.SUFFIX}'
    os.makedirs(os.path.dirname(_upload_path(rel)), exist_ok=True)
    with open(_upload_path(rel), 'wb') as fh:
        filecrypt.begin(fh)
    target = reply_target(thread, user, reply_to)
    info = {'name': clean_name(name), 'caption': (caption or '').strip()[:1000], 'silent': bool(silent),
            'schedule': str(schedule or ''), 'duration': sec, 'reply_to': target.pk if target else None}
    up = Upload.objects.create(thread=thread, user=user, kind=kind, path=rel, size=size,
                               info_enc=encrypt_text(thread.pk, json.dumps(info, ensure_ascii=False)))
    return {'upload': str(up.pk), 'part': PART, 'received': 0, 'size': size}


def _upload(user, upload_id, lock=False):
    from django.core.exceptions import ValidationError

    from .models import Upload
    qs = Upload.objects.select_for_update() if lock else Upload.objects
    try:
        up = qs.filter(pk=upload_id, user=user).select_related('thread').first()
    except (ValidationError, ValueError):
        up = None
    if up is None:
        raise ChatError(_('Загрузка не найдена — начните заново.'), 404)
    return up


def upload_status(user, upload_id) -> dict:
    up = _upload(user, upload_id)
    return {'upload': str(up.pk), 'part': PART, 'received': up.received, 'size': up.size}


def upload_part(user, upload_id, offset, data: bytes) -> dict:
    """Принять следующую часть. Не по порядку — вернуть, с какого места продолжать (409)."""
    from . import filecrypt
    from .media import video_ext
    with transaction.atomic():
        up = _upload(user, upload_id, lock=True)
        try:
            offset = int(offset)
        except (TypeError, ValueError):
            offset = -1
        if offset != up.received:
            err = ChatError(_('Часть файла пришла не по порядку'), 409)
            err.received = up.received
            raise err
        last = offset + len(data) == up.size
        if not data or len(data) > PART_MAX or offset + len(data) > up.size or (len(data) % filecrypt.CHUNK and not last):
            raise ChatError(_('Неверная часть файла'))
        if offset == 0 and up.kind == 'video' and not video_ext(data[:16]):
            raise ChatError(_('Неподдерживаемый формат файла'))
        with open(_upload_path(up.path), 'r+b') as fh:
            filecrypt.append(up.thread_id, fh, data, offset, up.size)
        up.received = offset + len(data)
        up.save(update_fields=['received'])
    return {'upload': str(up.pk), 'received': up.received, 'size': up.size}


def upload_finish(user, upload_id) -> dict:
    """Все части получены: превратить загрузку в сообщение и разослать участникам."""
    import json
    import os
    import uuid

    from . import filecrypt
    from .events import message_payload
    from .keyring import decrypt_text
    from .media import video_ext
    with transaction.atomic():
        up = _upload(user, upload_id, lock=True)
        if up.received != up.size:
            raise ChatError(_('Файл загружен не полностью'), 409)
        thread = up.thread
        _check_can_write(thread, user)
        info = json.loads(decrypt_text(thread.pk, up.info_enc))
        when = parse_schedule(info.get('schedule') or None)
        ext = 'bin'
        if up.kind == 'video':
            with open(_upload_path(up.path), 'rb') as fh:
                reader = filecrypt.Reader(thread.pk, fh, os.path.getsize(_upload_path(up.path)))
                ext = video_ext(b''.join(reader.iter_range(0, min(15, reader.size - 1)))) or 'mp4'
        now = timezone.now()
        rel = f'chat/{now:%Y}/{now:%m}/{uuid.uuid4().hex}.{ext}{filecrypt.SUFFIX}'
        os.makedirs(os.path.dirname(_upload_path(rel)), exist_ok=True)
        os.replace(_upload_path(up.path), _upload_path(rel))
        msg = Message(thread=thread, sender=user, kind=up.kind, duration=info.get('duration'), body=info.get('caption', ''),
                      silent=bool(info.get('silent')), scheduled_at=when,
                      reply_to=reply_target(thread, user, info.get('reply_to')))
        if up.kind == 'file':
            msg.set_meta(name=info.get('name', 'file'), size=up.size)
        msg.attachment.name = rel
        msg.save()
        _count_upload(user, up.size)
        kind = up.kind
        up.delete()
    if kind == 'video':
        from . import transcode
        transcode.schedule(msg.pk)
    if when:
        return message_payload(msg)
    _touch(thread, user)
    return _broadcast(msg)


def upload_cancel(user, upload_id) -> None:
    up = _upload(user, upload_id)
    _drop_upload(up)


def _drop_upload(up) -> None:
    import os
    try:
        os.remove(_upload_path(up.path))
    except OSError:
        pass
    up.delete()


def purge_uploads(now=None) -> int:
    """Удалить брошенные загрузки (старше суток) и их файлы — manage.py chat_send_due."""
    import os

    from .models import Upload
    now = now or timezone.now()
    old = list(Upload.objects.filter(created_at__lt=now - timedelta(hours=UPLOAD_TTL_HOURS)))
    for up in old:
        _drop_upload(up)
    tmp = _upload_path('chat/tmp')
    alive = {os.path.basename(p) for p in Upload.objects.values_list('path', flat=True)}
    if os.path.isdir(tmp):                       # файлы без записи в базе (чат удалён во время загрузки)
        for name in os.listdir(tmp):
            full = os.path.join(tmp, name)
            if name not in alive and now.timestamp() - os.path.getmtime(full) > UPLOAD_TTL_HOURS * 3600:
                try:
                    os.remove(full)
                except OSError:
                    pass
    return len(old)


# ---------- «Позвать поддержку»: сотрудник третьим в чате по объявлению, услуге, вакансии, с врачом ----------

NO_SUPPORT_CTX = ('', 'nikah', 'saved', 'support')        # личные чаты, никях, «Избранное» и сам чат поддержки — без этого


def support_state(thread, user) -> str:
    """Что показать в меню чата: 'call' — можно позвать поддержку, 'drop' — она уже здесь (можно отключить), '' — недоступно."""
    from apps.core.models import SiteSettings
    if thread.is_room or thread.context_type in NO_SUPPORT_CTX or not is_participant(thread, user):
        return ''
    support_id = SiteSettings.get_solo().support_user_id
    if not support_id:
        return ''
    return 'drop' if thread.observers.filter(pk=support_id).exists() else 'call'


def call_support(thread, user) -> None:
    """Пригласить аккаунт поддержки в этот чат. Он видит только то, что написано ПОСЛЕ приглашения (прошлая переписка
    для него закрыта — как «очищенная история»), может писать; обоим собеседникам об этом сообщает служебная запись."""
    from apps.core.models import Notification, SiteSettings

    from .models import ChatState
    if support_state(thread, user) != 'call':
        raise ChatError(_('В этом чате поддержку позвать нельзя.'), 400)
    from django.core.cache import cache
    key = f'support_call:{user.pk}'
    if cache.get(key, 0) >= 5:
        raise ChatError(_('Вы уже несколько раз звали поддержку сегодня. Напишите в чат поддержки.'), 429)
    cache.set(key, cache.get(key, 0) + 1, 86400)
    support = SiteSettings.get_solo().support_user
    thread.participants.add(support)
    thread.observers.add(support)
    ChatState.objects.update_or_create(thread=thread, user=support, defaults={'cleared_at': timezone.now(), 'hidden': False, 'archived': False})
    system_message(thread, user, str(_('Поддержка ilm4 приглашена в чат. Она видит сообщения, написанные после этого.')), broadcast=True)
    Notification.objects.create(user=support, text=str(_('Вас позвали в чат: {title}')).format(title=thread.subject or thread.title or f'#{thread.pk}'),
                                url=f'/chat/{thread.pk}/')


def drop_support(thread, user) -> None:
    """Отключить поддержку от чата (любой из собеседников или сама поддержка)."""
    from apps.core.models import SiteSettings
    support = SiteSettings.get_solo().support_user
    if support is None or thread.is_room or not is_participant(thread, user) or not thread.observers.filter(pk=support.pk).exists():
        raise ChatError(_('Поддержки в этом чате нет.'), 400)
    thread.observers.remove(support)
    thread.participants.remove(support)
    system_message(thread, user, str(_('Поддержка ilm4 отключена от чата.')), broadcast=True)


def system_message(thread, sender, text: str, duration=None, broadcast: bool = False) -> dict:
    """Служебная запись в переписке (открыт чат никяха, звонок 3:12, пропущенный)."""
    msg = Message.objects.create(thread=thread, sender=sender, kind=Message.SYSTEM, body=text, duration=duration)
    thread.save(update_fields=['updated_at'])
    from .models import ChatState
    ChatState.objects.filter(thread=thread, hidden=True).update(hidden=False)
    if broadcast:
        return _broadcast(msg)
    from .events import message_payload
    return message_payload(msg)


def delete_message(user, message_id, for_all: bool = True) -> dict:
    """Удалить сообщение. «У всех»: своё — автор, любое — владелец и админы группы / канала.
    «У себя» (for_all=False): сообщение остаётся у остальных, этот человек его больше не видит."""
    from . import rooms
    from .models import HiddenMessage
    msg = Message.objects.select_related('thread').filter(pk=message_id, scheduled_at__isnull=True).first()
    if msg is None or not can_read(msg.thread, user):
        raise ChatError(_('Сообщение не найдено'), 404)
    if not for_all:
        HiddenMessage.objects.get_or_create(user=user, message=msg)
        return {'ok': True, 'id': int(message_id), 'for_all': False}
    if msg.sender_id != user.pk and not (msg.thread.is_room and rooms.is_admin(msg.thread, user)):
        raise ChatError(_('Удалить у всех можно только своё сообщение.'), 403)
    thread_id, post_id = msg.thread_id, msg.comment_of_id
    if msg.attachment:
        msg.attachment.delete(save=False)
    msg.delete()
    if post_id:
        Message.objects.filter(pk=post_id, comments_count__gt=0).update(comments_count=F('comments_count') - 1)
    _group_send(thread_id, {'type': 'chat.deleted', 'ids': [int(message_id)]})
    return {'ok': True, 'id': int(message_id), 'for_all': True}


def _group_send(thread_id, event: dict) -> None:
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    layer = get_channel_layer()
    if layer is not None:
        async_to_sync(layer.group_send)(f'chat_{thread_id}', event)


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
    _touch(msg.thread, msg.sender)


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


# ---------- свои папки, архив, закреп, ответы, реакции, пересылка (как в Telegram) ----------
# Код — в folders.py и msgops.py; снаружи зовут только отсюда.
from .folders import (  # noqa: F401
    clear_history,
    delete_folder,
    folder_summary,
    hide_chat,
    recommended_folders,
    reorder_folders,
    save_folder,
    set_archived,
    set_draft,
    set_folder_chat,
    set_pinned,
    set_unread,
    state_of,
    user_folders,
)
from .msgops import (  # noqa: F401
    add_comment,
    comments_of,
    edit_message,
    forward_messages,
    message_raw,
    open_saved,
    pin_message,
    pinned_messages,
    react,
    search_messages,
    window_around,
)
