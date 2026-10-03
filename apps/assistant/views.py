"""Страница ИИ-помощника на сайте: разговор, свой ключ, прошлые разговоры."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.decorators import module_required

from . import services
from .models import Chat
from .services import AssistantError


@login_required
@module_required('assistant')
def index(request, chat_id=None):
    chat = get_object_or_404(Chat, pk=chat_id, user=request.user) if chat_id else None
    return render(request, 'assistant/index.html', {
        'chat': chat, 'items': services.transcript(chat) if chat else [], 'chats': services.chats(request.user),
        'st': services.state(request.user), 'brief': None if chat else services.briefing(request.user), 'active_section': 'assistant'})


@login_required
@module_required('assistant')
@require_POST
def send(request):
    try:
        return JsonResponse(services.send(request.user, request.POST.get('text', ''), request.POST.get('chat') or None))
    except AssistantError as exc:
        return JsonResponse({'error': exc.message}, status=exc.status)


@login_required
@require_POST
def key(request):
    try:
        services.set_key(request.user, request.POST.get('key', ''), request.POST.get('provider', 'anthropic'),
                         request.POST.get('model', ''), request.POST.get('base_url', ''))
        messages.success(request, _('Сохранено.'))
    except AssistantError as exc:
        messages.error(request, exc.message)
    return redirect('assistant:index')


@login_required
@require_POST
def prefs(request):
    services.set_prefs(request.user, request.POST.get('read_chats') == '1')
    return redirect('assistant:index')


@login_required
@require_POST
def delete(request, chat_id):
    services.delete_chat(request.user, chat_id)
    return redirect('assistant:index')
