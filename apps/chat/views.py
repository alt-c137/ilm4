"""Чат: список диалогов, окно, создание диалога (fallback без WebSocket)."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.views.decorators.http import require_POST

from apps.accounts import phone_verify
from apps.core.decorators import module_required

from . import rooms, services
from .events import preview
from .models import Message, Thread
from .services import ChatError, UploadRefused, nikah_contacts_forbidden, send_text, store_upload  # noqa: F401
from .services import blocked as _blocked
from .services import flags as _flags

User = get_user_model()
HISTORY = 300
WEEKDAYS = [_lazy('пн'), _lazy('вт'), _lazy('ср'), _lazy('чт'), _lazy('пт'), _lazy('сб'), _lazy('вс')]


def _when(dt):
    """Время для списка диалогов, как в Telegram: 14:05 · вчера · пн · 12.09.25."""
    if dt is None:
        return ''
    local = timezone.localtime(dt)
    today = timezone.localdate()
    if local.date() == today:
        return local.strftime('%H:%M')
    if local.date() == today - timedelta(days=1):
        return _('вчера')
    if (today - local.date()).days < 7:
        return WEEKDAYS[local.weekday()]
    return local.strftime('%d.%m.%y')


def _day_label(d):
    today = timezone.localdate()
    if d == today:
        return _('Сегодня')
    if d == today - timedelta(days=1):
        return _('Вчера')
    return date_format(d, 'j E' if d.year == today.year else 'j E Y')


def _rows(user):
    """Диалоги пользователя для списка: собеседник (или группа / канал), последнее сообщение, непрочитанные."""
    from .views_rooms import pic
    rows = []
    for thread, other, last in services.inbox(user):
        who = pic(thread, other, user)
        rows.append({
            'thread': thread,
            'other': other,
            'pic': who,
            'name': who['name'],
            'last': last,
            'mine': bool(last and last.sender_id == user.id),
            # в группе перед текстом — кто написал
            'author': last.sender.get_display_name() if last and thread.kind == Thread.GROUP and last.sender_id != user.id
                      and last.kind != Message.SYSTEM else '',
            'preview': preview(last) if last else '',
            'kind': last.kind if last else '',
            'when': _when(last.created_at if last else thread.updated_at),
            'unread': thread.unread,
            'muted': bool(thread.muted),
            'hue': who['hue'],
            'folder': thread.folder,
        })
    return rows


def _side(request):
    """Список чатов с папками (как папки Telegram): ?f=buy — только «Покупки»."""
    rows = _rows(request.user)
    folders = services.folders_for(request.user, rows)
    current = request.GET.get('f', '')
    if current not in {f['key'] for f in folders}:
        current = ''
    f = _flags()
    return {'rows': [r for r in rows if not current or r['folder'] == current], 'folders': folders,
            'folder': current, 'all_unread': sum(r['unread'] for r in rows), 'support_on': bool(services.support_user()),
            'rooms_on': f['groups'] or f['channels'], 'channels_on': f['channels']}


@login_required
@module_required('chat')
def inbox(request):
    return render(request, 'chat/inbox.html', _side(request))


def _person_row(u, viewer) -> dict:
    from apps.accounts import people
    return {'id': u.pk, 'name': u.get_display_name(), 'handle': u.handle or '', 'city': u.city,
            'avatar': u.avatar.url if u.avatar else '', 'hue': u.pk % 7, 'letter': (u.get_display_name() or '?')[:1].upper(),
            'online': people.quick_online(u, viewer), 'verified': u.platform_verified,
            'chat': f"{reverse('chat:start')}?user={u.pk}", 'profile': reverse('accounts:public', args=[u.pk])}


@login_required
@module_required('chat')
def people(request):
    """«Новое сообщение» — как в Telegram: поиск человека по @имени или номеру, свои контакты,
    кнопки «Новая группа» и «Новый канал». ?json=1 — для поиска без перезагрузки страницы."""
    from apps.accounts import people as ppl
    q = request.GET.get('q', '').strip()
    me = request.user
    known = ppl.contacts(me)
    found, hint = [], ''
    if q:
        try:
            found = ppl.search(me, q)
        except ppl.PeopleError as exc:
            hint = exc.message
        low = q.lstrip('@').lower()
        ids = {u.pk for u in found}
        known = [u for u in known if low in f'{u.get_display_name()} {u.handle or ""}'.lower() and u.pk not in ids]
        if not found and not known and not hint:
            hint = _('Никого не нашли. Ищите по имени пользователя (@имя) или по номеру телефона целиком — '
                     'находятся те, кто разрешил искать себя по номеру.')
    data = {'found': [_person_row(u, me) for u in found], 'contacts': [_person_row(u, me) for u in known], 'hint': hint}
    if request.GET.get('json'):
        return JsonResponse(data)
    f = _flags()
    return render(request, 'chat/people.html', {
        **data, 'q': q, 'can_group': rooms.can_create(me, Thread.GROUP), 'can_channel': rooms.can_create(me, Thread.CHANNEL),
        'channels_on': f['channels'], 'contacts_on': f['contacts'], 'support_on': bool(services.support_user()),
        'active_section': 'chat'})


@login_required
@module_required('chat')
@require_POST
def mute(request, pk):
    """«Без звука» / со звуком для любого чата (кнопка «Звук» в профиле собеседника и в шапке чата)."""
    thread = get_object_or_404(Thread, pk=pk)
    if not services.can_read(thread, request.user):
        raise Http404
    try:
        services.set_muted(thread, request.user, not services.is_muted(thread, request.user))
    except ChatError as exc:
        messages.error(request, exc.message)
    nxt = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = reverse('chat:thread', args=[pk])
    return redirect(nxt)


@login_required
@module_required('chat')
def thread_detail(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    if not services.can_read(thread, request.user):
        return redirect('chat:inbox')  # чужой диалог — не показываем и без 404
    blocked = _blocked(thread, request.user)
    if request.method == 'POST':  # fallback без JS: отправить обычной формой
        try:
            send_text(thread, request.user, request.POST.get('body', '')[:2000],
                      silent=request.POST.get('silent') == '1', schedule=request.POST.get('schedule'))
        except ChatError as exc:
            messages.error(request, exc.message)
        return redirect('chat:thread', pk=pk)
    services.mark_read(thread, request.user)          # открыл диалог — входящие прочитаны

    from . import contexts
    items, prev, risky = [], None, contexts.risky(thread)
    group = thread.kind == Thread.GROUP
    # последние HISTORY сообщений: длинная переписка не грузит страницу целиком
    msgs = list(services.visible_messages(thread, request.user).select_related('sender')
                .order_by('-created_at', '-pk')[:HISTORY])[::-1]
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
            'warn': risky and m.sender_id != request.user.id and contexts.is_scam(m.body),
            'meta': _file_meta(m),
            # группа: имя автора над первым сообщением серии
            'who': m.sender.get_display_name() if group and m.sender_id != request.user.id
                   and (not prev or prev.sender_id != m.sender_id or prev.kind == Message.SYSTEM) else '',
            'hue': m.sender_id % 7,
        })
        prev = m
    from .views_rooms import pic
    other = None if thread.is_room else thread.other_participant(request.user)
    info = services.thread_info(thread, request.user)
    room = info['room']
    who = pic(thread, other, request.user)
    presence = None
    if other is not None:
        from apps.accounts import people as ppl
        presence = ppl.presence(other, request.user)
        presence['text'] = ppl.status_text(presence)
    return render(request, 'chat/thread.html', {
        'thread': thread,
        'other': other,
        'presence': presence,
        'muted': services.is_muted(thread, request.user),
        'pic': who,
        'hue': who['hue'],
        'items': items,
        **_side(request),
        'info': info,
        'room': room,
        'can_post': room['can_post'] if room else True,
        'blocked': blocked,
        'witnesses': [u.get_display_name() for u in thread.observers.exclude(pk=request.user.pk)],
        'chat_cfg': {'me': request.user.id, 'thread': thread.pk, 'other': who['name'], 'features': _flags(thread),
                     'room': thread.kind if thread.is_room else '', 'admin': bool(room and room['admin']),
                     'warn_text': contexts.warn_text() if risky else ''},
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
        from apps.accounts.models import UserBlock
        if other and UserBlock.between(request.user, other):
            messages.error(request, _('Переписка недоступна: один из вас заблокировал другого.'))
            return redirect('chat:inbox')
        if other:
            from apps.accounts import people
            subject = request.POST.get('subject') or request.GET.get('subject') or ''
            ctx = (request.GET.get('ctx', ''), request.GET.get('ctx_id', ''))      # чат по объявлению
            try:
                if not ctx[0] and services.direct_between(request.user, other) is None:
                    people.check_new_chat(request.user, other)                     # против рассылок незнакомым
                thread = services.open_direct(request.user, other, subject, context=ctx if ctx[0] else None)
            except (ChatError, people.PeopleError) as exc:
                messages.error(request, exc.message)
                return redirect('chat:inbox')
            call = request.GET.get('call', '')                 # кнопки «Звонок» / «Видео» в профиле человека
            url = reverse('chat:thread', args=[thread.pk])
            return redirect(f'{url}?call={call}' if call in ('audio', 'video') else url)
        messages.error(request, _('Пользователь с таким email не найден.'))
    return render(request, 'chat/start.html', {'email': email})


@login_required
@module_required('chat')
@require_POST
def upload(request, pk):
    """Фото / видео / голосовое / кружок: сохранить (зашифрованным) и разослать участникам."""
    thread = get_object_or_404(Thread, pk=pk)
    try:
        payload = store_upload(thread, request.user, request.POST.get('kind', ''), request.FILES.get('file'),
                               request.POST.get('duration'), request.POST.get('caption', ''),
                               silent=request.POST.get('silent') == '1', schedule=request.POST.get('schedule'))
    except ChatError as exc:
        return JsonResponse({'error': exc.message}, status=exc.status)
    return JsonResponse(payload)


def _file_meta(m) -> dict:
    if m.kind != 'file':
        return {}
    from .media import is_risky_name
    meta = m.meta
    return {**meta, 'risky': is_risky_name(meta.get('name', ''))}


def read_part(request) -> bytes:
    """Тело запроса с частью файла (сырые байты). Больше положенного не читаем."""
    try:
        declared = int(request.headers.get('Content-Length') or 0)
    except ValueError:
        declared = 0
    if declared > services.PART_MAX:
        raise ChatError(_('Неверная часть файла'), 413)
    return request.read(services.PART_MAX + 1)


def upload_step(request, user, step, upload_id=None, thread=None) -> dict:
    """Шаги загрузки большого файла — общие для сайта и API приложения."""
    if step == 'begin':
        d = getattr(request, 'data', None) or request.POST          # приложение шлёт JSON, сайт — форму
        return services.upload_begin(thread, user, d.get('kind', 'file'), d.get('name', ''), d.get('size'),
                                     d.get('duration'), d.get('caption', ''),
                                     silent=str(d.get('silent', '')).lower() in ('1', 'true'),
                                     schedule=d.get('schedule') or None)
    if step == 'part':
        return services.upload_part(user, upload_id, request.GET.get('offset'), read_part(request))
    if step == 'finish':
        return services.upload_finish(user, upload_id)
    if step == 'cancel':
        services.upload_cancel(user, upload_id)
        return {'ok': True}
    if step == 'status':
        return services.upload_status(user, upload_id)
    raise Http404


def _upload_error(exc) -> JsonResponse:
    data = {'error': exc.message}
    if hasattr(exc, 'received'):
        data['received'] = exc.received              # с какого места продолжать
    return JsonResponse(data, status=exc.status)


@login_required
@module_required('chat')
@require_POST
def upload_begin(request, pk):
    """Большой файл или видео: начать загрузку частями (до 2 ГБ, как в Telegram)."""
    thread = get_object_or_404(Thread, pk=pk)
    try:
        return JsonResponse(upload_step(request, request.user, 'begin', thread=thread))
    except ChatError as exc:
        return _upload_error(exc)


@login_required
@module_required('chat')
def upload_chunk(request, upload_id, step='status'):
    if (step == 'status') != (request.method == 'GET'):
        return JsonResponse({'error': 'method'}, status=405)
    try:
        return JsonResponse(upload_step(request, request.user, step, upload_id))
    except ChatError as exc:
        return _upload_error(exc)


@login_required
@require_POST
def scheduled_action(request, msg_id, action):
    """Своё запланированное сообщение: «отправить сейчас» или «удалить»."""
    try:
        if action == 'send':
            return JsonResponse(services.send_scheduled_now(request.user, msg_id))
        if action == 'cancel':
            services.cancel_scheduled(request.user, msg_id)
            return JsonResponse({'ok': True, 'id': msg_id})
        if action == 'delete':
            return JsonResponse(services.delete_message(request.user, msg_id))
    except ChatError as exc:
        return JsonResponse({'error': exc.message}, status=exc.status)
    raise Http404


@login_required
def attachment(request, msg_id):
    """Вложение — только участникам диалога."""
    from .media import serve

    msg = get_object_or_404(Message.objects.select_related('thread'), pk=msg_id)
    if (not msg.attachment or not services.can_read(msg.thread, request.user)
            or (msg.scheduled_at and msg.sender_id != request.user.pk)):
        raise Http404
    name = msg.meta.get('name', 'file') if msg.kind == Message.FILE else ''
    return serve(request, msg.attachment, msg.thread_id, download_name=name)


@login_required
@module_required('chat')
def support(request):
    """Чат с командой ilm4."""
    try:
        thread = services.open_support(request.user)
    except ChatError as exc:
        messages.info(request, exc.message)
        return redirect('core:support')
    return redirect('chat:thread', pk=thread.pk)


@login_required
@module_required('chat')
@phone_verify.required('contacts')
def contacts(request):
    """«Найти знакомых»: кто из контактов телефона уже в ilm4."""
    if not _flags()['contacts']:
        raise Http404
    return render(request, 'chat/contacts.html', {'has_phone': bool(request.user.phone)})


@login_required
@require_POST
@phone_verify.required('contacts')
def contacts_match(request):
    """Принимает SHA-256 последних 9 цифр номеров (не сами номера), возвращает
    тех, кто разрешил находить себя. Не чаще 10 раз в час — защита от перебора."""
    import json

    from django.core.cache import cache

    if not _flags()['contacts']:
        raise Http404
    key = f'contacts_match:{request.user.pk}'
    hits = cache.get(key, 0)
    if hits >= 10:
        return JsonResponse({'error': _('Слишком часто. Попробуйте через час.')}, status=429)
    cache.set(key, hits + 1, 3600)
    try:
        keys = json.loads(request.body or b'{}').get('keys', [])
    except ValueError:
        return JsonResponse({'error': _('Неверный запрос')}, status=400)
    keys = [k for k in keys if isinstance(k, str) and len(k) == 64][:2000]
    found = (User.objects.filter(phone_key__in=keys, findable_by_phone=True, is_active=True)
             .exclude(pk=request.user.pk)[:200])
    return JsonResponse({'users': [{
        'id': u.pk, 'name': u.get_display_name(), 'city': u.city,
        'avatar': u.avatar.url if u.avatar else '', 'hue': u.pk % 7,
        'chat': f"{reverse('chat:start')}?user={u.pk}", 'profile': reverse('accounts:public', args=[u.pk]),
    } for u in found]})
