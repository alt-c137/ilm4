"""API чата: диалоги, сообщения, отправка текста и вложений, «прочитано», файлы.

Живые сообщения приложение получает по тому же WebSocket, что и сайт
(/ws/chat/<id>/, вход по заголовку Authorization — см. apps/api/ws.py).
"""
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from apps.chat import services
from apps.chat.events import message_payload, preview
from apps.chat.models import Message, Thread
from apps.chat.services import ChatError

from .base import ApiError, abs_url, api, as_int, file_url

HISTORY_PAGE = 50


def _thread(request, pk) -> Thread:
    thread = get_object_or_404(Thread, pk=pk)
    if not thread.participants.filter(pk=request.user.pk).exists():
        raise Http404
    return thread


def _info(request, thread) -> dict:
    """Тип чата: папка, карточка объявления (ссылки — полные), подсказка раздела."""
    info = services.thread_info(thread, request.user)
    card = info['card']
    if card:
        card['url'] = abs_url(request, card['url']) if card['url'] else ''
        card['image'] = abs_url(request, card['image']) if card['image'] else ''
        for a in card['actions']:
            a['text'] = a['text'].replace('{link}', abs_url(request, a.pop('path')))
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
    from django.db.models import Count, Q

    from apps.nikah.models import NikahMatch

    user = request.user
    qs = (user.chat_threads.all().prefetch_related('participants')
          .annotate(unread=Count('messages', filter=Q(messages__read_at__isnull=True)
                                 & Q(messages__scheduled_at__isnull=True) & ~Q(messages__sender=user))))
    nikah = set(NikahMatch.objects.filter(thread__in=qs).values_list('thread_id', flat=True))
    items = []
    for t in qs[:300]:
        last = services.visible_messages(t, user).order_by('-created_at').select_related('sender').first()
        other = t.other_participant(user)
        items.append({
            'id': t.pk, 'title': other.get_display_name() if other else (t.title or t.subject or _('Диалог')),
            'subject': t.subject, 'other_id': other.pk if other else None,
            'avatar': file_url(request, other.avatar) if other else '',
            'preview': str(preview(last)) if last else '', 'kind': last.kind if last else '',
            'mine': bool(last and last.sender_id == user.pk),
            'updated_at': (last.created_at if last else t.updated_at).isoformat(),
            'unread': t.unread, 'nikah': t.pk in nikah, 'folder': t.folder, 'context': t.context_type,
        })
    return {'items': items, 'folders': services.folders_for(user, items), 'support': bool(services.support_user())}


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
    other = thread.other_participant(request.user)
    if not before:
        services.mark_read(thread, request.user)
    return {
        'items': [_msg(request, m) for m in reversed(chunk[:HISTORY_PAGE])],
        'more': len(chunk) > HISTORY_PAGE,
        'thread': {'id': thread.pk, 'subject': thread.subject,
                   'title': other.get_display_name() if other else (thread.title or _('Диалог')),
                   'other_id': other.pk if other else None,
                   'avatar': file_url(request, other.avatar) if other else '',
                   'blocked': services.blocked(thread, request.user), 'features': {
                       k: v for k, v in services.flags(thread).items() if k != 'turn'},
                   'turn': services.flags(thread).get('turn'),
                   'witnesses': [u.get_display_name() for u in thread.observers.exclude(pk=request.user.pk)],
                   **_info(request, thread),
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


def _saved(payload) -> Message:
    return Message.objects.select_related('sender').get(pk=payload['id'])


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
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
    raise Http404


@api(auth=True, module='chat')
def file(request, msg_id):
    from apps.chat.media import serve
    m = get_object_or_404(Message.objects.select_related('thread'), pk=msg_id)
    if (not m.attachment or not m.thread.participants.filter(pk=request.user.pk).exists()
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
