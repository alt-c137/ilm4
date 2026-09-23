"""Чат: список диалогов, окно, создание диалога (fallback без WebSocket)."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from apps.core.decorators import module_required

from .events import preview
from .models import Message, Thread

User = get_user_model()
WEEKDAYS = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']


def _when(dt):
    """Время для списка диалогов, как в Telegram: 14:05 · вчера · пн · 12.09.25."""
    if dt is None:
        return ''
    local = timezone.localtime(dt)
    today = timezone.localdate()
    if local.date() == today:
        return local.strftime('%H:%M')
    if local.date() == today - timedelta(days=1):
        return 'вчера'
    if (today - local.date()).days < 7:
        return WEEKDAYS[local.weekday()]
    return local.strftime('%d.%m.%y')


def _day_label(d):
    today = timezone.localdate()
    if d == today:
        return 'Сегодня'
    if d == today - timedelta(days=1):
        return 'Вчера'
    return date_format(d, 'j E' if d.year == today.year else 'j E Y')


def _rows(user):
    """Диалоги пользователя для списка: собеседник, последнее сообщение, непрочитанные."""
    threads = (user.chat_threads.all().prefetch_related('participants')
               .annotate(unread=Count('messages', filter=Q(messages__read_at__isnull=True)
                                      & ~Q(messages__sender=user))))
    rows = []
    for thread in threads:
        last = thread.messages.order_by('-created_at').select_related('sender').first()
        other = thread.other_participant(user)
        rows.append({
            'thread': thread,
            'other': other,
            'last': last,
            'mine': bool(last and last.sender_id == user.id),
            'preview': preview(last) if last else '',
            'kind': last.kind if last else '',
            'when': _when(last.created_at if last else thread.updated_at),
            'unread': thread.unread,
            'hue': (other.pk if other else 0) % 7,
        })
    return rows


@login_required
@module_required('chat')
def inbox(request):
    return render(request, 'chat/inbox.html', {'rows': _rows(request.user)})


@login_required
@module_required('chat')
def thread_detail(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    if request.user not in thread.participants.all():
        return redirect('chat:inbox')  # чужой диалог — не показываем и без 404
    if request.method == 'POST':  # fallback без JS: отправить обычной формой
        body = request.POST.get('body', '').strip()[:2000]
        if body:
            Message.objects.create(thread=thread, sender=request.user, body=body)
        return redirect('chat:thread', pk=pk)
    # открыл диалог — входящие прочитаны
    thread.messages.filter(read_at__isnull=True).exclude(sender=request.user) \
        .update(read_at=timezone.now())

    items, prev = [], None
    msgs = list(thread.messages.select_related('sender'))
    for i, m in enumerate(msgs):
        local = timezone.localtime(m.created_at)
        nxt = msgs[i + 1] if i + 1 < len(msgs) else None
        items.append({
            'm': m,
            'mine': m.sender_id == request.user.id,
            'day': _day_label(local.date()) if not prev or timezone.localtime(prev.created_at).date() != local.date() else '',
            'time': local.strftime('%H:%M'),
            'dur': f'{(m.duration or 0) // 60}:{(m.duration or 0) % 60:02d}',
            # «хвостик» — у последнего в серии сообщений одного автора
            'tail': not nxt or nxt.sender_id != m.sender_id
                    or timezone.localtime(nxt.created_at).date() != local.date(),
        })
        prev = m
    other = thread.other_participant(request.user)
    return render(request, 'chat/thread.html', {
        'thread': thread,
        'other': other,
        'hue': (other.pk if other else 0) % 7,
        'items': items,
        'rows': _rows(request.user),
        'chat_cfg': {'me': request.user.id, 'thread': thread.pk,
                     'other': other.get_display_name() if other else '', 'features': _flags()},
    })


@login_required
@module_required('chat')
def thread_start(request):
    """Начать диалог по email участника (например, с карточки объявления)."""
    email = request.POST.get('email', '').strip().lower() if request.method == 'POST' \
        else request.GET.get('email', '').strip().lower()
    uid = request.GET.get('user', '')
    if uid.isdigit() and int(uid) != request.user.pk:
        # по id — не раскрываем email собеседника в ссылках
        email = User.objects.filter(pk=int(uid), is_active=True).values_list('email', flat=True).first() or ''
    if email and email != request.user.email.lower():
        other = User.objects.filter(email__iexact=email).first()
        if other:
            thread = (Thread.objects.filter(participants=request.user)
                      .filter(participants=other).first())
            subject = (request.POST.get('subject') or request.GET.get('subject') or '').strip()[:160]
            if not thread:
                thread = Thread.objects.create(subject=subject)
                thread.participants.add(request.user, other)
            elif subject and thread.subject != subject:
                # новый разговор о другом товаре/маршруте — обновляем тему диалога
                thread.subject = subject
                thread.save(update_fields=['subject', 'updated_at'])
            return redirect('chat:thread', pk=thread.pk)
        messages.error(request, 'Пользователь с таким email не найден.')
    return render(request, 'chat/start.html', {'email': email})


def _flags():
    from apps.core.models import SiteSettings
    st = SiteSettings.get_solo()
    return {'photo': st.chat_photos_enabled, 'voice': st.chat_voice_enabled, 'circle': st.chat_circles_enabled,
            'calls': st.chat_calls_enabled, 'video_calls': st.chat_video_calls_enabled,
            'turn': {'url': st.webrtc_turn_url, 'username': st.webrtc_turn_username,
                     'credential': st.webrtc_turn_credential} if st.webrtc_turn_url else None}


@login_required
@module_required('chat')
@require_POST
def upload(request, pk):
    """Фото / голосовое / кружок: сохранить и разослать участникам по WebSocket."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from .events import message_payload, notify_recipients, preview
    from .media import MediaError, prepare

    thread = get_object_or_404(Thread, pk=pk)
    if request.user not in thread.participants.all():
        return JsonResponse({'error': 'Нет доступа'}, status=403)
    kind = request.POST.get('kind', '')
    if not _flags().get(kind):
        return JsonResponse({'error': 'Эта функция сейчас отключена'}, status=403)
    upload_file = request.FILES.get('file')
    if not upload_file:
        return JsonResponse({'error': 'Файл не получен'}, status=400)
    try:
        content, duration = prepare(kind, upload_file, request.POST.get('duration'))
    except MediaError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    msg = Message(thread=thread, sender=request.user, kind=kind, duration=duration,
                  body=request.POST.get('caption', '').strip()[:1000])
    msg.attachment.save(content.name, content, save=False)
    msg.save()
    thread.save(update_fields=['updated_at'])
    payload = message_payload(msg)
    layer = get_channel_layer()
    if layer is not None:
        async_to_sync(layer.group_send)(f'chat_{thread.pk}', {'type': 'chat.message', 'payload': payload})
    notify_recipients(thread, request.user, preview(msg))
    return JsonResponse(payload)


@login_required
def attachment(request, msg_id):
    """Вложение — только участникам диалога."""
    from .media import serve

    msg = get_object_or_404(Message.objects.select_related('thread'), pk=msg_id)
    if not msg.attachment or not msg.thread.participants.filter(pk=request.user.pk).exists():
        raise Http404
    return serve(request, msg.attachment)


@login_required
@module_required('chat')
def contacts(request):
    """«Найти знакомых»: кто из контактов телефона уже в ilm4."""
    return render(request, 'chat/contacts.html', {'has_phone': bool(request.user.phone)})


@login_required
@require_POST
def contacts_match(request):
    """Принимает SHA-256 последних 9 цифр номеров (не сами номера), возвращает
    тех, кто разрешил находить себя. Не чаще 10 раз в час — защита от перебора."""
    import json

    from django.core.cache import cache

    key = f'contacts_match:{request.user.pk}'
    hits = cache.get(key, 0)
    if hits >= 10:
        return JsonResponse({'error': 'Слишком часто. Попробуйте через час.'}, status=429)
    cache.set(key, hits + 1, 3600)
    try:
        keys = json.loads(request.body or b'{}').get('keys', [])
    except ValueError:
        return JsonResponse({'error': 'Неверный запрос'}, status=400)
    keys = [k for k in keys if isinstance(k, str) and len(k) == 64][:2000]
    found = (User.objects.filter(phone_key__in=keys, findable_by_phone=True, is_active=True)
             .exclude(pk=request.user.pk)[:200])
    return JsonResponse({'users': [{
        'id': u.pk, 'name': u.get_display_name(), 'city': u.city,
        'avatar': u.avatar.url if u.avatar else '', 'hue': u.pk % 7,
        'chat': f"{reverse('chat:start')}?user={u.pk}", 'profile': reverse('accounts:public', args=[u.pk]),
    } for u in found]})
