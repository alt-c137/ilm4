"""API ИИ-помощника для приложения: состояние, разговор, свой ключ."""
from django.shortcuts import get_object_or_404

from apps.assistant import services
from apps.assistant.models import Chat
from apps.assistant.services import AssistantError

from .base import ApiError, api


def _wrap(fn):
    try:
        return fn()
    except AssistantError as exc:
        raise ApiError(exc.message, exc.status) from exc


@api(auth=True, module='assistant')
def state(request):
    chat = None
    if request.GET.get('chat'):
        chat = get_object_or_404(Chat, pk=request.GET['chat'], user=request.user)
    return {**services.state(request.user), 'brief': services.briefing(request.user), 'chats': services.chats(request.user),
            'chat': chat.pk if chat else None, 'messages': services.transcript(chat) if chat else []}


@api(methods=('POST',), auth=True, module='assistant')
def send(request):
    d = request.data
    return _wrap(lambda: services.send(request.user, str(d.get('text', '')), d.get('chat') or None))


@api(methods=('POST',), auth=True, module='assistant')
def key(request):
    """Свой ИИ: {key, provider, model} — сохранить; {key: ''} — убрать ключ; {read_chats: bool} — разрешение читать сообщения."""
    d = request.data
    if 'read_chats' in d:
        services.set_prefs(request.user, str(d.get('read_chats')).lower() in ('1', 'true', 'on'))
    if 'key' in d:
        _wrap(lambda: services.set_key(request.user, str(d.get('key', '')), str(d.get('provider', 'anthropic')),
                                       str(d.get('model', '')), str(d.get('base_url', ''))))
    return services.state(request.user)


@api(methods=('POST',), auth=True, module='assistant')
def delete(request, chat_id):
    services.delete_chat(request.user, chat_id)
    return {'ok': True}
