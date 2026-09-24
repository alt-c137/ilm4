"""API чата: диалоги, сообщения, отправка текста и вложений, «прочитано», файлы.

Живые сообщения приложение получает по тому же WebSocket, что и сайт
(/ws/chat/<id>/, вход по заголовку Authorization — см. apps/api/ws.py).
"""
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.chat.events import message_payload, preview
from apps.chat.models import Message, Thread
from apps.chat.views import UploadRefused, _blocked, _flags, send_text, store_upload

from .base import ApiError, abs_url, api, as_int, file_url

HISTORY_PAGE = 50


def _thread(request, pk) -> Thread:
    thread = get_object_or_404(Thread, pk=pk)
    if not thread.participants.filter(pk=request.user.pk).exists():
        raise Http404
    return thread


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
          .annotate(unread=Count('messages', filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=user))))
    nikah = set(NikahMatch.objects.filter(thread__in=qs).values_list('thread_id', flat=True))
    items = []
    for t in qs[:300]:
        last = t.messages.order_by('-created_at').select_related('sender').first()
        other = t.other_participant(user)
        items.append({
            'id': t.pk, 'title': other.get_display_name() if other else (t.title or t.subject or _('Диалог')),
            'subject': t.subject, 'other_id': other.pk if other else None,
            'avatar': file_url(request, other.avatar) if other else '',
            'preview': str(preview(last)) if last else '', 'kind': last.kind if last else '',
            'mine': bool(last and last.sender_id == user.pk),
            'updated_at': (last.created_at if last else t.updated_at).isoformat(),
            'unread': t.unread, 'nikah': t.pk in nikah,
        })
    return {'items': items}


@api(auth=True, module='chat')
def messages(request, pk):
    """Сообщения: последние 50; ?before=<id> — более ранние (прокрутка вверх)."""
    from apps.nikah.models import NikahMatch

    thread = _thread(request, pk)
    qs = thread.messages.select_related('sender').order_by('-created_at', '-pk')
    before = as_int(request.GET.get('before'))
    if before:
        qs = qs.filter(pk__lt=before)
    chunk = list(qs[:HISTORY_PAGE + 1])
    other = thread.other_participant(request.user)
    if not before:
        thread.messages.filter(read_at__isnull=True).exclude(sender=request.user).update(read_at=timezone.now())
    return {
        'items': [_msg(request, m) for m in reversed(chunk[:HISTORY_PAGE])],
        'more': len(chunk) > HISTORY_PAGE,
        'thread': {'id': thread.pk, 'subject': thread.subject,
                   'title': other.get_display_name() if other else (thread.title or _('Диалог')),
                   'other_id': other.pk if other else None,
                   'avatar': file_url(request, other.avatar) if other else '',
                   'blocked': _blocked(thread, request.user), 'features': {
                       k: v for k, v in _flags(thread).items() if k != 'turn'},
                   'witnesses': [u.get_display_name() for u in thread.observers.exclude(pk=request.user.pk)],
                   'nikah': NikahMatch.objects.filter(thread=thread).exists()},
    }


@api(methods=('POST',), auth=True, module='chat')
def send(request, pk):
    thread = _thread(request, pk)
    try:
        return _msg(request, _saved(send_text(thread, request.user, str(request.data.get('body', '')))))
    except UploadRefused as exc:
        raise ApiError(exc.message, exc.status) from exc


@api(methods=('POST',), auth=True, module='chat')
def upload(request, pk):
    thread = _thread(request, pk)
    try:
        payload = store_upload(thread, request.user, request.POST.get('kind', ''), request.FILES.get('file'),
                               request.POST.get('duration'), request.POST.get('caption', ''))
    except UploadRefused as exc:
        raise ApiError(exc.message, exc.status) from exc
    return _msg(request, _saved(payload))


def _saved(payload) -> Message:
    return Message.objects.select_related('sender').get(pk=payload['id'])


@api(methods=('POST',), auth=True, module='chat')
def read(request, pk):
    thread = _thread(request, pk)
    n = thread.messages.filter(read_at__isnull=True).exclude(sender=request.user).update(read_at=timezone.now())
    return {'ok': True, 'updated': n}


@api(auth=True, module='chat')
def file(request, msg_id):
    from apps.chat.media import serve
    m = get_object_or_404(Message.objects.select_related('thread'), pk=msg_id)
    if not m.attachment or not m.thread.participants.filter(pk=request.user.pk).exists():
        raise Http404
    return serve(request, m.attachment)
