"""API чата: диалоги, сообщения, отправка текста и вложений, «прочитано», файлы.

Живые сообщения приложение получает по тому же WebSocket, что и сайт
(/ws/chat/<id>/, вход по заголовку Authorization — см. apps/api/ws.py).
"""
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from apps.chat import rooms, services
from apps.chat.events import message_payload, preview
from apps.chat.models import Message, Thread
from apps.chat.services import ChatError

from .base import ApiError, abs_url, api, as_int, file_url

HISTORY_PAGE = 50


def _thread(request, pk) -> Thread:
    """Чат, который человеку можно открыть: свой диалог, своя группа / канал или публичные."""
    thread = get_object_or_404(Thread, pk=pk)
    if not services.can_read(thread, request.user):
        raise Http404
    return thread


def _face(request, thread, other) -> dict:
    """Название и аватар для списка и шапки: у группы / канала — свои, у диалога — собеседника."""
    if thread.is_room:
        return {'title': thread.title, 'avatar': file_url(request, thread.avatar), 'other_id': None,
                'room': thread.kind, 'members': thread.members_count, 'verified': thread.platform_verified,
                'online': False}
    from apps.accounts import people
    return {'title': other.get_display_name() if other else (thread.title or thread.subject or _('Диалог')),
            'avatar': file_url(request, other.avatar) if other else '', 'other_id': other.pk if other else None,
            'room': '', 'members': 0, 'verified': bool(other and other.platform_verified),
            'online': bool(other and people.quick_online(other, request.user))}


def _room_card(request, t, mine=()) -> dict:
    return {'id': t.pk, 'kind': t.kind, 'title': t.title, 'about': t.about, 'handle': t.handle or '',
            'avatar': file_url(request, t.avatar), 'members': t.members_count, 'verified': t.platform_verified,
            'member': t.pk in mine}


def _info(request, thread) -> dict:
    """Тип чата: папка, карточка объявления (ссылки — полные), подсказка раздела."""
    info = services.thread_info(thread, request.user)
    card = info['card']
    if card:
        card['url'] = abs_url(request, card['url']) if card['url'] else ''
        card['image'] = abs_url(request, card['image']) if card['image'] else ''
        for a in card['actions']:
            a['text'] = a['text'].replace('{link}', abs_url(request, a.pop('path')))
    room = info.get('room')
    if room:                                    # ссылки, которыми делятся
        room['invite_link'] = abs_url(request, f'/chat/join/{thread.invite_code}/') if room['invite'] else ''
        room['public_link'] = abs_url(request, f'/c/{thread.handle}/') if thread.is_public and thread.handle else ''
    return info


def _msg(request, m) -> dict:
    data = message_payload(m)
    data['url'] = abs_url(request, f'/api/v1/chat/file/{m.pk}/') if m.attachment else ''
    data['mine'] = m.sender_id == request.user.pk
    data['read'] = bool(m.read_at)
    data['iso'] = m.created_at.isoformat()
    return data


@api(auth=True, module='chat')
def threads(request):
    from apps.nikah.models import NikahMatch

    user = request.user
    rows = services.inbox(user)
    nikah = set(NikahMatch.objects.filter(thread__in=[t.pk for t, _o, _m in rows]).values_list('thread_id', flat=True))
    items = []
    for t, other, last in rows:
        items.append({
            'id': t.pk, **_face(request, t, other), 'subject': t.subject, 'muted': bool(t.muted),
            'author': last.sender.get_display_name() if last and t.kind == Thread.GROUP and last.sender_id != user.pk
                      and last.kind != Message.SYSTEM else '',
            'preview': str(preview(last)) if last else '', 'kind': last.kind if last else '',
            'mine': bool(last and last.sender_id == user.pk), 'read': bool(last and last.read_at),
            'updated_at': (last.created_at if last else t.updated_at).isoformat(),
            'unread': t.unread, 'nikah': t.pk in nikah, 'folder': t.folder, 'context': t.context_type,
        })
    f = services.flags()
    return {'items': items, 'folders': services.folders_for(user, items), 'support': bool(services.support_user()),
            'can_group': rooms.can_create(user, Thread.GROUP), 'can_channel': rooms.can_create(user, Thread.CHANNEL),
            'channels': f['channels']}


@api(auth=True, module='chat')
def messages(request, pk):
    """Сообщения: последние 50; ?before=<id> — более ранние (прокрутка вверх)."""
    from apps.nikah.models import NikahMatch

    thread = _thread(request, pk)
    qs = services.visible_messages(thread, request.user).select_related('sender').order_by('-created_at', '-pk')
    before = as_int(request.GET.get('before'))
    if before:
        qs = qs.filter(pk__lt=before)
    chunk = list(qs[:HISTORY_PAGE + 1])
    for m in chunk:
        m.thread = thread                       # иначе каждое сообщение отдельно ходило бы в базу за чатом
    other = None if thread.is_room else thread.other_participant(request.user)
    if not before:
        services.mark_read(thread, request.user)
    from apps.accounts import people
    return {
        'items': [_msg(request, m) for m in reversed(chunk[:HISTORY_PAGE])],
        'more': len(chunk) > HISTORY_PAGE,
        'thread': {'id': thread.pk, 'subject': thread.subject, **_face(request, thread, other),
                   'blocked': services.blocked(thread, request.user), 'features': {
                       k: v for k, v in services.flags(thread).items() if k != 'turn'},
                   'turn': services.flags(thread).get('turn'),
                   'witnesses': [u.get_display_name() for u in thread.observers.exclude(pk=request.user.pk)],
                   **_info(request, thread),
                   'presence': people.presence(other, request.user) if other else None,
                   'handle': (other.handle or '') if other else '',
                   'muted': services.is_muted(thread, request.user),
                   'nikah': NikahMatch.objects.filter(thread=thread).exists()},
    }


@api(methods=('POST',), auth=True, module='chat')
def send(request, pk):
    thread = _thread(request, pk)
    try:
        return _msg(request, _saved(services.send_text(
            thread, request.user, str(request.data.get('body', '')), silent=bool(request.data.get('silent')),
            schedule=request.data.get('schedule') or None)))
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc


@api(methods=('POST',), auth=True, module='chat')
def upload(request, pk):
    thread = _thread(request, pk)
    try:
        payload = services.store_upload(thread, request.user, request.POST.get('kind', ''), request.FILES.get('file'),
                                        request.POST.get('duration'), request.POST.get('caption', ''),
                                        silent=request.POST.get('silent') in ('1', 'true'),
                                        schedule=request.POST.get('schedule') or None)
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    return _msg(request, _saved(payload))


@api(methods=('POST',), auth=True, module='chat')
def upload_begin(request, pk):
    """Большой файл или видео частями: начать. Дальше — upload_step (part → finish)."""
    from apps.chat.views import upload_step
    thread = _thread(request, pk)
    try:
        return upload_step(request, request.user, 'begin', thread=thread)
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc


@api(methods=('GET', 'POST'), auth=True, module='chat')
def upload_chunk(request, upload_id, step='status'):
    from django.http import JsonResponse

    from apps.chat.views import upload_step
    if (step == 'status') != (request.method == 'GET'):
        raise ApiError('method', 405)
    try:
        result = upload_step(request, request.user, step, upload_id)
    except ChatError as exc:
        if hasattr(exc, 'received'):
            return JsonResponse({'error': exc.message, 'received': exc.received}, status=exc.status)
        raise ApiError(exc.message, exc.status) from exc
    return _msg(request, _saved(result)) if step == 'finish' else result


def _saved(payload) -> Message:
    return Message.objects.select_related('sender').get(pk=payload['id'])


@api(methods=('POST',), auth=True, module='chat')
def mute(request, pk):
    """«Без звука» для любого чата: {'on': true|false}."""
    thread = _thread(request, pk)
    on = str(request.data.get('on', '1')).lower() in ('1', 'true', 'on')
    try:
        services.set_muted(thread, request.user, on)
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    return {'muted': on}


@api(auth=True, module='chat')
def media(request, pk):
    """Вложения чата для вкладок профиля: ?what=media|files|voice, ?before=<id> — дальше."""
    thread = _thread(request, pk)
    try:
        rows = services.shared_media(thread, request.user, request.GET.get('what', 'media'),
                                     before=as_int(request.GET.get('before')))
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    return {'items': [_msg(request, m) for m in rows], 'more': len(rows) >= 60}


@api(methods=('POST',), auth=True, module='chat')
def read(request, pk):
    thread = _thread(request, pk)
    return {'ok': True, 'updated': services.mark_read(thread, request.user)}


@api(methods=('POST',), auth=True, module='chat')
def scheduled(request, msg_id, action):
    """Своё запланированное: send — отправить сейчас, cancel — удалить."""
    try:
        if action == 'send':
            return _msg(request, _saved(services.send_scheduled_now(request.user, msg_id)))
        if action == 'cancel':
            services.cancel_scheduled(request.user, msg_id)
            return {'ok': True}
        if action == 'delete':
            return services.delete_message(request.user, msg_id)
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    raise Http404


@api(auth=True, module='chat')
def file(request, msg_id):
    from apps.chat.media import serve
    m = get_object_or_404(Message.objects.select_related('thread'), pk=msg_id)
    if (not m.attachment or not services.can_read(m.thread, request.user)
            or (m.scheduled_at and m.sender_id != request.user.pk)):
        raise Http404
    name = m.meta.get('name', 'file') if m.kind == Message.FILE else ''
    return serve(request, m.attachment, m.thread_id, download_name=name)


@api(methods=('POST',), auth=True, module='chat')
def support(request):
    """Открыть чат с командой ilm4."""
    try:
        return {'thread': services.open_support(request.user).pk}
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc


# ---------- группы и каналы ----------

def _room(request, pk) -> Thread:
    thread = get_object_or_404(Thread, pk=pk)
    if not thread.is_room or not rooms.enabled(thread.kind):
        raise Http404
    return thread


def _room_full(request, thread) -> dict:
    info = rooms.info(thread, request.user)
    people = []
    if info['member'] and (thread.kind == Thread.GROUP or info['admin']):
        people = [{'id': m.user_id, 'name': m.user.get_display_name(), 'avatar': file_url(request, m.user.avatar),
                   'role': m.role, 'role_name': str(m.get_role_display())} for m in rooms.members(thread, 100)]
    return {**_room_card(request, thread), **info,
            'invite_link': abs_url(request, f'/chat/join/{thread.invite_code}/') if info['invite'] else '',
            'public_link': abs_url(request, f'/c/{thread.handle}/') if thread.is_public and thread.handle else '',
            'people': people}


@api(auth=True, module='chat')
def rooms_catalog(request):
    """Публичные каналы и группы (поиск ?q=, вид ?kind=channel|group)."""
    from .base import page
    qs = rooms.catalog(request.GET.get('q', ''), request.GET.get('kind', ''))
    mine = set(Thread.objects.filter(participants=request.user).exclude(kind=Thread.DIRECT).values_list('pk', flat=True))
    return page(request, qs, lambda t: _room_card(request, t, mine))


@api(methods=('POST',), auth=True, module='chat')
def room_create(request):
    d = request.data
    try:
        thread = rooms.create(request.user, str(d.get('kind', '')), str(d.get('title', '')), str(d.get('about', '')),
                              is_public=str(d.get('is_public', '')).lower() in ('1', 'true', 'on'),
                              handle=str(d.get('handle', '')), avatar=request.FILES.get('avatar'))
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    return {'thread': thread.pk}


@api(methods=('GET', 'POST'), auth=True, module='chat')
def room(request, pk):
    """Сведения о группе / канале; POST — изменить (владелец и админы)."""
    thread = _room(request, pk)
    if not services.can_read(thread, request.user):
        raise Http404
    if request.method == 'POST':
        try:
            rooms.update(thread, request.user, request.data, avatar=request.FILES.get('avatar'))
        except ChatError as exc:
            raise ApiError(exc.message, exc.status) from exc
    return _room_full(request, thread)


@api(methods=('POST',), auth=True, module='chat')
def room_act(request, pk, action):
    """join · leave · mute · unmute · invite (новая ссылка) · delete."""
    thread = _room(request, pk)
    user = request.user
    try:
        if action == 'join':
            rooms.join(thread, user, str(request.data.get('code', '')))
        elif action == 'leave':
            rooms.leave(thread, user)
            return {'ok': True, 'left': True}
        elif action in ('mute', 'unmute'):
            rooms.set_muted(thread, user, action == 'mute')
        elif action == 'invite':
            rooms.reset_invite(thread, user)
        elif action == 'delete':
            rooms.delete(thread, user)
            return {'ok': True, 'left': True}
        else:
            raise Http404
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    thread.refresh_from_db()
    return _room_full(request, thread)


@api(methods=('POST',), auth=True, module='chat')
def room_member(request, pk, user_id, action):
    """admin · unadmin · remove — владелец и админы."""
    from django.contrib.auth import get_user_model
    thread = _room(request, pk)
    target = get_object_or_404(get_user_model(), pk=user_id)
    try:
        if action == 'remove':
            rooms.remove_member(thread, request.user, target)
        elif action in ('admin', 'unadmin'):
            rooms.set_admin(thread, request.user, target, action == 'admin')
        else:
            raise Http404
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    thread.refresh_from_db()
    return _room_full(request, thread)


@api(methods=('GET', 'POST'), auth=True, module='chat')
def room_link(request, code):
    """Ссылка-приглашение: GET — куда зовут, POST — вступить."""
    thread = rooms.by_code(code)
    if thread is None or not rooms.enabled(thread.kind):
        raise Http404
    if request.method == 'POST':
        try:
            rooms.join(thread, request.user, code)
        except ChatError as exc:
            raise ApiError(exc.message, exc.status) from exc
        thread.refresh_from_db()
    mine = {thread.pk} if services.is_participant(thread, request.user) else set()
    return _room_card(request, thread, mine)


@api(auth=True, module='chat')
def room_handle(request, handle):
    """Канал по публичному имени (ссылка ilm4.com/c/имя/, открытая в приложении)."""
    thread = rooms.by_handle(handle)
    if thread is None or not thread.is_public or not rooms.enabled(thread.kind):
        raise Http404
    mine = {thread.pk} if services.is_participant(thread, request.user) else set()
    return _room_card(request, thread, mine)

