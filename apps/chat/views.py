"""Чат: список диалогов, окно, создание диалога (fallback без WebSocket)."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import module_required

from .models import Message, Thread

User = get_user_model()


@login_required
@module_required('chat')
def inbox(request):
    rows = []
    for thread in request.user.chat_threads.all().prefetch_related('participants'):
        rows.append({
            'thread': thread,
            'other': thread.other_participant(request.user),
            'last': thread.messages.order_by('-created_at').first(),
        })
    return render(request, 'chat/inbox.html', {'rows': rows})


@login_required
@module_required('chat')
def thread_detail(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    if request.user not in thread.participants.all():
        return redirect('chat:inbox')  # чужой диалог — не показываем и без 404
    if request.method == 'POST':  # fallback без JS: отправить обычной формой
        body = request.POST.get('body', '').strip()
        if body:
            Message.objects.create(thread=thread, sender=request.user, body=body)
        return redirect('chat:thread', pk=pk)
    return render(request, 'chat/thread.html', {
        'thread': thread,
        'messages': thread.messages.select_related('sender'),
    })


@login_required
@module_required('chat')
def thread_start(request):
    """Начать диалог по email участника (например, с карточки объявления)."""
    email = request.POST.get('email', '').strip().lower() if request.method == 'POST' \
        else request.GET.get('email', '').strip().lower()
    if email and email != request.user.email.lower():
        other = User.objects.filter(email__iexact=email).first()
        if other:
            thread = (Thread.objects.filter(participants=request.user)
                      .filter(participants=other).first())
            if not thread:
                thread = Thread.objects.create(
                    subject=request.POST.get('subject', '').strip()[:160])
                thread.participants.add(request.user, other)
            return redirect('chat:thread', pk=thread.pk)
        messages.error(request, 'Пользователь с таким email не найден.')
    return render(request, 'chat/start.html', {'email': email})
