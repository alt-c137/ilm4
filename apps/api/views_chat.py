"""API чата: диалоги, сообщения, отправка текста и вложений, «прочитано», файлы.

Живые сообщения приложение получает по тому же WebSocket, что и сайт
(/ws/chat/<id>/, вход по заголовку Authorization — см. apps/api/ws.py).
"""
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from apps.chat import rooms, services
from apps.chat.events import decorate, message_payload, preview
from apps.chat.models import ChatFolder, Message, Reaction, Thread
from apps.chat.msgops import EDIT_HOURS
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
                'online': False, 'saved': False}
    if thread.is_saved:
        return {'title': str(_('Избранное')), 'avatar': '', 'other_id': None, 'room': '', 'members': 0,
                'verified': False, 'online': False, 'saved': True}
    from apps.accounts import people
    from apps.chat import persona
    masked = persona.mask(thread, other)
    if masked:                                   # чат никяха: имя из анкеты, основной профиль не раскрываем
        return {'title': masked['name'], 'avatar': abs_url(request, masked['avatar']) if masked.get('avatar') else '',
                'other_id': masked.get('user_id'), 'room': '', 'members': 0, 'verified': False,
                'online': False, 'saved': False, 'masked': True, 'nikah_profile': masked['profile_id']}
    return {'title': people.shown_name(other, request.user) if other else (thread.title or thread.subject or _('Диалог')),
            'avatar': file_url(request, other.avatar) if other else '', 'other_id': other.pk if other else None,
            'room': '', 'members': 0, 'verified': bool(other and other.platform_verified),
            'online': bool(other and people.quick_online(other, request.user)), 'saved': False}


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
    if '_my' not in m.__dict__ and m.pk:
        data['my_reaction'] = (Reaction.objects.filter(message=m, user=request.user).values_list('emoji', flat=True).first()
                               or '') if data['reactions'] else ''
    data['url'] = abs_url(request, f'/api/v1/chat/file/{m.pk}/') if m.attachment else ''
    data['mine'] = m.sender_id == request.user.pk
    data['iso'] = m.created_at.isoformat()
    return data


@api(auth=True, module='chat')
def threads(request):
    """Список чатов + вкладки-папки (свои папки, «Все», архив) — как в Telegram."""
    from apps.nikah.models import NikahMatch

    user = request.user
    rows = services.inbox(user)
    nikah = set(NikahMatch.objects.filter(thread__in=[t.pk for t, _o, _m in rows]).values_list('thread_id', flat=True))
    items = []
    for t, other, last in rows:
        face = _face(request, t, other)
        t.list_name = face['title']
        items.append({
            'id': t.pk, **face, 'subject': '' if t.is_saved else t.subject, 'muted': bool(t.muted),
            'author': last.sender.get_display_name() if last and t.kind == Thread.GROUP and last.sender_id != user.pk
                      and last.kind != Message.SYSTEM else '',
            'preview': str(preview(last)) if last else '', 'kind': last.kind if last else '',
            'mine': bool(last and last.sender_id == user.pk and not t.is_saved), 'read': bool(last and last.read_at),
            'updated_at': (last.created_at if last else t.updated_at).isoformat(),
            'unread': t.unread, 'unread_mark': t.unread_mark, 'pinned': bool(t.pinned_at), 'archived': t.archived,
            'draft': t.draft, 'type': t.chat_type,
            'nikah': t.pk in nikah, 'folder': t.folder, 'context': t.context_type,
        })
    f = services.flags()
    return {'items': items, 'tabs': services.folder_summary(user, [t for t, _o, _m in rows]),
            'support': bool(services.support_user()),
            'can_group': rooms.can_create(user, Thread.GROUP), 'can_channel': rooms.can_create(user, Thread.CHANNEL),
            'channels': f['channels']}


@api(auth=True, module='chat')
def messages(request, pk):
    """Сообщения: последние 50; ?before=<id> — более ранние (прокрутка вверх); ?after=<id> — более поздние;
    ?around=<id> — «окно» вокруг сообщения (переход к ответу, закрепу, найденному)."""
    from apps.nikah.models import NikahMatch

    thread = _thread(request, pk)
    user = request.user
    base = services.visible_messages(thread, user).select_related('sender', 'reply_to__sender')
    before, after, around = (as_int(request.GET.get(k)) for k in ('before', 'after', 'around'))
    more, more_after = False, False
    if around:
        try:
            win = services.window_around(thread, user, around, half=HISTORY_PAGE // 2)
        except ChatError as exc:
            raise ApiError(exc.message, exc.status) from exc
        rows, more, more_after = win['items'], win['more_before'], win['more_after']
    elif after:
        pivot = base.filter(pk=after).values_list('created_at', flat=True).first()
        chunk = list(base.filter(created_at__gt=pivot).order_by('created_at', 'pk')[:HISTORY_PAGE + 1]) if pivot else []
        rows, more_after = chunk[:HISTORY_PAGE], len(chunk) > HISTORY_PAGE
    else:
        qs = base.order_by('-created_at', '-pk')
        if before:
            pivot = base.filter(pk=before).values_list('created_at', flat=True).first()
            qs = qs.filter(created_at__lte=pivot).exclude(pk=before) if pivot else qs.none()
        chunk = list(qs[:HISTORY_PAGE + 1])
        rows, more = chunk[:HISTORY_PAGE][::-1], len(chunk) > HISTORY_PAGE
    for m in rows:
        m.thread = thread                       # иначе каждое сообщение отдельно ходило бы в базу за чатом
    decorate(rows, user)
    other = None if thread.is_room or thread.is_saved else thread.other_participant(user)
    if not before and not after and not around:
        services.mark_read(thread, user)
    from apps.accounts import people
    info = _info(request, thread)
    room = info.get('room')
    pins = services.pinned_messages(thread, user)
    decorate(pins, user)
    from apps.core import ads
    ad = ads.for_thread(thread) if not before and not after and not around else None
    if ad:
        ad = {**ad, 'image': abs_url(request, ad['image']) if ad['image'] else '', 'url': abs_url(request, ad['url'])}
    return {
        'items': [_msg(request, m) for m in rows],
        'more': more, 'more_after': more_after, 'ad': ad,
        'thread': {'id': thread.pk, 'subject': thread.subject, **_face(request, thread, other),
                   'blocked': services.blocked(thread, user), 'features': {
                       k: v for k, v in services.flags(thread).items() if k != 'turn'},
                   'turn': services.flags(thread).get('turn'),
                   'witnesses': [u.get_display_name() for u in thread.observers.exclude(pk=user.pk)],
                   **info,
                   'presence': people.presence(other, user) if other else None,
                   'handle': (other.handle or '') if other else '',
                   'muted': services.is_muted(thread, user),
                   'nikah': NikahMatch.objects.filter(thread=thread).exists(),
                   # как в Telegram: закреп, реакции, запрет пересылки, срок правки, комментарии, черновик
                   'pins': [_msg(request, m) for m in pins],
                   'draft': services._draft_text(thread.pk, services.state_of(thread, user)),
                   'can_pin': bool(room['admin']) if room else True,
                   'member': bool(room['member']) if room else True,
                   'protected': thread.protected or services.is_nikah(thread.pk),
                   'reactions': Reaction.EMOJI if thread.reactions_on else [],
                   'comments': bool(thread.is_channel and thread.comments_on),
                   'edit_hours': 0 if thread.is_channel else EDIT_HOURS},
    }


@api(methods=('POST',), auth=True, module='chat')
def send(request, pk):
    thread = _thread(request, pk)
    try:
        return _msg(request, _saved(services.send_text(
            thread, request.user, str(request.data.get('body', '')), silent=bool(request.data.get('silent')),
            schedule=request.data.get('schedule') or None, reply_to=request.data.get('reply_to'))))
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc


@api(methods=('POST',), auth=True, module='chat')
def upload(request, pk):
    thread = _thread(request, pk)
    try:
        payload = services.store_upload(thread, request.user, request.POST.get('kind', ''), request.FILES.get('file'),
                                        request.POST.get('duration'), request.POST.get('caption', ''),
                                        silent=request.POST.get('silent') in ('1', 'true'),
                                        schedule=request.POST.get('schedule') or None,
                                        reply_to=request.POST.get('reply_to') or None)
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
    return Message.objects.select_related('sender', 'reply_to__sender').get(pk=payload['id'])


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
    """Действия с сообщением. Запланированное: send — отправить сейчас, cancel — удалить.
    Обычное: delete (у всех) · hide (у себя) · edit {body} · raw · pin · unpin · react {emoji}."""
    user = request.user
    try:
        if action == 'send':
            return _msg(request, _saved(services.send_scheduled_now(user, msg_id)))
        if action == 'cancel':
            services.cancel_scheduled(user, msg_id)
            return {'ok': True}
        if action in ('delete', 'hide'):
            return services.delete_message(user, msg_id, for_all=action == 'delete')
        if action == 'edit':
            return _msg(request, _saved(services.edit_message(user, msg_id, str(request.data.get('body', '')))))
        if action == 'raw':
            return {'id': msg_id, 'body': services.message_raw(user, msg_id)}
        if action in ('pin', 'unpin'):
            return _msg(request, _saved(services.pin_message(user, msg_id, action == 'pin')))
        if action == 'react':
            return services.react(user, msg_id, str(request.data.get('emoji', '')))
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    raise Http404


# ---------- как в Telegram: состояние чата, папки, пересылка, поиск, «Избранное», комментарии ----------

@api(methods=('POST',), auth=True, module='chat')
def state(request, pk, action):
    """pin · unpin · archive · unarchive · unread · read · mute · unmute · clear · hide · folder_add · folder_remove.
    {'folder': id} — закреп в своей папке / добавить в папку."""
    thread = get_object_or_404(Thread, pk=pk)
    user = request.user
    folder = ChatFolder.objects.filter(user=user, pk=as_int(request.data.get('folder'))).first()
    try:
        if action in ('pin', 'unpin'):
            services.set_pinned(thread, user, action == 'pin', folder=folder)
        elif action in ('archive', 'unarchive'):
            services.set_archived(thread, user, action == 'archive')
        elif action in ('unread', 'read'):
            services.set_unread(thread, user, action == 'unread')
        elif action in ('mute', 'unmute'):
            services.set_muted(thread, user, action == 'mute')
        elif action == 'clear':
            services.clear_history(thread, user)
        elif action == 'hide':
            services.hide_chat(thread, user)
        elif action == 'support_call':
            services.call_support(thread, user)
        elif action == 'support_drop':
            services.drop_support(thread, user)
        elif action in ('folder_add', 'folder_remove') and folder is not None:
            services.set_folder_chat(user, folder.pk, thread, action == 'folder_add')
        else:
            raise Http404
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    return {'ok': True}


@api(methods=('POST',), auth=True, module='chat')
def draft(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    try:
        services.set_draft(thread, request.user, str(request.data.get('text', '')))
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    return {'ok': True}


def _folder_json(f) -> dict:
    return {'id': f.pk, 'title': f.title, 'emoji': f.emoji, 'types': f.types, 'no_muted': f.no_muted,
            'no_read': f.no_read, 'no_archived': f.no_archived,
            'include': [t.pk for t in f.include.all()], 'exclude': [t.pk for t in f.exclude.all()]}


@api(methods=('GET', 'POST'), auth=True, module='chat')
def folders(request):
    """Свои папки. POST: {title, emoji, types[], no_muted, no_read, no_archived, include[], exclude[]} — создать;
    {'order': [id…]} — свой порядок вкладок; {'recommended': 'personal'} — добавить готовую папку."""
    from apps.chat import folders as fl
    user = request.user
    if request.method == 'POST':
        d = request.data
        try:
            if 'order' in d:
                services.reorder_folders(user, d.get('order') or [])
            elif d.get('recommended'):
                preset = next((r for r in fl.RECOMMENDED if r['key'] == d.get('recommended')), None)
                if preset is None:
                    raise Http404
                services.save_folder(user, {**preset, 'title': str(preset['title'])})
            else:
                services.save_folder(user, d)
        except ChatError as exc:
            raise ApiError(exc.message, exc.status) from exc
    return {'items': [_folder_json(f) for f in services.user_folders(user)],
            'recommended': [{'key': r['key'], 'title': r['title'], 'emoji': r['emoji'], 'hint': r['hint']}
                            for r in services.recommended_folders(user)],
            'types': fl.folder_types(), 'max': ChatFolder.MAX_FOLDERS}


@api(methods=('GET', 'POST', 'DELETE'), auth=True, module='chat')
def folder(request, pk):
    f = get_object_or_404(ChatFolder, pk=pk, user=request.user)
    if request.method == 'DELETE':
        services.delete_folder(request.user, f.pk)
        return {'ok': True}
    if request.method == 'POST':
        try:
            f = services.save_folder(request.user, request.data, f)
        except ChatError as exc:
            raise ApiError(exc.message, exc.status) from exc
    return _folder_json(ChatFolder.objects.prefetch_related('include', 'exclude').get(pk=f.pk))


@api(methods=('POST',), auth=True, module='chat')
def forward(request):
    """Переслать: {'ids': [сообщения], 'to': [чаты или 'saved'], 'hide': скрыть автора}."""
    d = request.data
    try:
        sent = services.forward_messages(request.user, d.get('ids') or [], d.get('to') or [], hide_sender=bool(d.get('hide')))
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    return {'ok': True, 'count': len(sent), 'threads': sorted({p['thread'] for p in sent if 'thread' in p})}


@api(auth=True, module='chat')
def search(request, pk):
    thread = _thread(request, pk)
    found = services.search_messages(thread, request.user, request.GET.get('q', ''))
    return {'items': [{'id': m.pk, 'name': m.sender.get_display_name(), 'text': m.body[:160],
                       'iso': m.created_at.isoformat()} for m in found]}


@api(methods=('POST',), auth=True, module='chat')
def saved(request):
    """«Избранное» — чат с самим собой."""
    return {'thread': services.open_saved(request.user).pk}


@api(methods=('GET', 'POST'), auth=True, module='chat')
def post(request, pk, msg_id):
    """Комментарии под постом канала: GET — список, POST {body, reply_to} — написать."""
    thread = _thread(request, pk)
    try:
        if request.method == 'POST':
            services.add_comment(request.user, msg_id, str(request.data.get('body', '')), request.data.get('reply_to'))
        data = services.comments_of(request.user, msg_id)
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    if data['post'].thread_id != thread.pk:
        raise Http404
    rows = [data['post'], *data['items']]
    decorate(rows, request.user)
    return {'post': _msg(request, data['post']), 'items': [_msg(request, m) for m in data['items']],
            'can_write': rooms.membership(thread, request.user) is not None and not thread.closed}


@api(auth=True, module='chat')
def file(request, msg_id):
    from apps.chat.media import serve
    m = get_object_or_404(Message.objects.select_related('thread'), pk=msg_id)
    if (not m.attachment or not services.can_read(m.thread, request.user)
            or (m.scheduled_at and m.sender_id != request.user.pk)
            or (not m.comment_of_id and not services.visible_messages(m.thread, request.user).filter(pk=m.pk).exists())):
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



@api(methods=('GET', 'POST'), auth=True, module='chat')
def find(request):
    """Единый поиск: ?q= → люди (@имя, номер), каналы и группы, сообщества, сообщения во всех моих чатах."""
    from apps.chat import finder

    from .views_people import person_card
    if request.method == 'POST':                       # открыл что-то из поиска — в «Недавние»; {clear: true} — очистить
        if request.data.get('clear'):
            finder.forget_recent(request.user)
        else:
            finder.remember(request.user, str(request.data.get('kind', '')), request.data.get('id'))
        return {'ok': True}
    if not request.GET.get('q', '').strip():
        # поиск ещё пуст: «частые» (кому пишет чаще всего) и «недавние» (что открывал из поиска) — как в Telegram
        from apps.accounts import people
        top = [{'thread': t.pk, 'id': o.pk, 'name': people.shown_name(o, request.user), 'avatar': file_url(request, o.avatar)}
               for t, o in finder.top_people(request.user)]
        rec = []
        for kind, obj in finder.recent(request.user):
            if kind == 'u':
                rec.append({'kind': 'u', 'id': obj.pk, 'title': people.shown_name(obj, request.user), 'sub': f'@{obj.handle}' if obj.handle else '',
                            'avatar': file_url(request, obj.avatar)})
            elif kind == 's':
                rec.append({'kind': 's', 'id': obj.pk, 'title': obj.title, 'sub': str(_('сообщество')), 'avatar': file_url(request, obj.icon)})
            else:
                face = _face(request, obj, None if obj.is_room or obj.is_saved else obj.other_participant(request.user))
                rec.append({'kind': 't', 'id': obj.pk, 'title': str(face['title']), 'avatar': face['avatar'], 'saved': face.get('saved', False),
                            'sub': str(_('канал')) if obj.is_channel else str(_('группа')) if obj.is_room else ''})
        return {'top': top, 'recent': rec}
    data = finder.find(request.user, request.GET.get('q', ''))
    mine = set(Thread.objects.filter(participants=request.user).exclude(kind=Thread.DIRECT).values_list('pk', flat=True))
    return {'people': [person_card(request, u) for u in data['people']],
            'rooms': [_room_card(request, t, mine) for t in data['rooms']],
            'spaces': [{'id': s.pk, 'title': s.title, 'icon': file_url(request, s.icon), 'members': s.members_count,
                        'verified': s.platform_verified} for s in data['spaces']],
            'messages': data['messages']}
