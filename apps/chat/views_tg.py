"""Список чатов и переписка «как в Telegram»: свои папки, архив, закреп, «не прочитано», черновик,
пересылка, поиск по чату, «Избранное», комментарии к постам канала, ссылки вида /@имя/."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.decorators import module_required

from . import folders, rooms, services
from .events import decorate, message_payload
from .models import ChatFolder, Thread
from .services import ChatError

User = get_user_model()
EMOJI = ['📁', '👤', '👥', '📢', '🛍', '💼', '🤝', '⭐', '❤️', '🔔', '🕌', '📚', '🏠', '✈️', '🎓', '💬']


def _ajax(request) -> bool:
    return request.headers.get('X-Requested-With') == 'fetch' or 'application/json' in request.headers.get('Accept', '')


def _back(request, default='chat:inbox'):
    nxt = request.POST.get('next') or request.GET.get('next') or ''
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = reverse(default)
    return redirect(nxt)


def _done(request, data=None, error=None, status=400):
    """Ответ на действие: приложению-странице — JSON, обычной форме — возврат назад с сообщением."""
    if _ajax(request):
        return JsonResponse({'error': error}, status=status) if error else JsonResponse(data or {'ok': True})
    if error:
        messages.error(request, error)
    return _back(request)


# ---------- состояние чата: закреп, архив, «не прочитано», очистка, удаление у себя ----------

@login_required
@module_required('chat')
@require_POST
def state(request, pk, action):
    thread = get_object_or_404(Thread, pk=pk)
    user = request.user
    folder = None
    fid = request.POST.get('folder', '')
    if fid.isdigit():
        folder = ChatFolder.objects.filter(user=user, pk=int(fid)).first()
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
        elif action in ('folder_add', 'folder_remove') and folder is not None:
            services.set_folder_chat(user, folder.pk, thread, action == 'folder_add')
        else:
            raise Http404
    except ChatError as exc:
        return _done(request, error=exc.message, status=exc.status)
    return _done(request)


@login_required
@module_required('chat')
@require_POST
def draft(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    try:
        services.set_draft(thread, request.user, request.POST.get('text', ''))
    except ChatError as exc:
        return JsonResponse({'error': exc.message}, status=exc.status)
    return JsonResponse({'ok': True})


# ---------- папки ----------

def _chat_choices(user, saved: bool = True) -> list:
    """Чаты человека для выбора «включить / исключить» и для пересылки."""
    from .views_rooms import pic
    out = []
    for thread, other, _last in services.inbox(user):
        who = pic(thread, other, user)
        if thread.is_saved and not saved:
            continue
        out.append({'id': thread.pk, 'name': who['name'], 'pic': who, 'type': thread.chat_type,
                    'can_post': rooms.can_post(thread, user) if thread.is_room else not services.blocked(thread, user)})
    return out


@login_required
@module_required('chat')
def folder_list(request):
    """«Папки с чатами» — как в настройках Telegram: свои папки, порядок, рекомендованные."""
    user = request.user
    if request.method == 'POST':
        what = request.POST.get('what', '')
        try:
            if what == 'order':
                services.reorder_folders(user, request.POST.getlist('ids'))
            elif what == 'move':
                ids = [f.pk for f in services.user_folders(user)]
                pk, by = int(request.POST.get('id', 0)), int(request.POST.get('by', 0))
                if pk in ids:
                    i = ids.index(pk)
                    j = max(0, min(len(ids) - 1, i + by))
                    ids.insert(j, ids.pop(i))
                    services.reorder_folders(user, ids)
            elif what == 'delete':
                services.delete_folder(user, request.POST.get('id'))
            elif what == 'recommended':
                preset = next((r for r in folders.RECOMMENDED if r['key'] == request.POST.get('key')), None)
                if preset:
                    services.save_folder(user, {**preset, 'title': str(preset['title'])})
        except (ChatError, ValueError) as exc:
            messages.error(request, getattr(exc, 'message', str(exc)))
        return redirect('chat:folders')
    return render(request, 'chat/folders.html', {
        'folders': services.user_folders(user), 'recommended': services.recommended_folders(user),
        'max': ChatFolder.MAX_FOLDERS, 'active_section': 'chat'})


@login_required
@module_required('chat')
def folder_edit(request, pk=None):
    user = request.user
    folder = get_object_or_404(ChatFolder, pk=pk, user=user) if pk else None
    if request.method == 'POST':
        data = {'title': request.POST.get('title', ''), 'emoji': request.POST.get('emoji', ''),
                'types': request.POST.getlist('types'), 'no_muted': request.POST.get('no_muted', ''),
                'no_read': request.POST.get('no_read', ''), 'no_archived': request.POST.get('no_archived', ''),
                'include': request.POST.getlist('include'), 'exclude': request.POST.getlist('exclude')}
        try:
            saved = services.save_folder(user, data, folder)
        except ChatError as exc:
            messages.error(request, exc.message)
            return redirect(request.path)
        return redirect(f"{reverse('chat:inbox')}?f={saved.pk}")
    chats = _chat_choices(user)
    inc = {t.pk for t in folder.include.all()} if folder else set()
    exc = {t.pk for t in folder.exclude.all()} if folder else set()
    return render(request, 'chat/folder_form.html', {
        'folder': folder, 'types': folders.folder_types(), 'chats': chats, 'inc': inc, 'exc': exc, 'emoji': EMOJI,
        'active_section': 'chat'})


# ---------- пересылка, поиск, закреп, «Избранное» ----------

@login_required
@module_required('chat')
def pick(request):
    """Мои чаты для окна «Переслать» (JSON): сначала «Избранное», затем по времени."""
    rows = [{'id': c['id'], 'name': c['name'], 'url': c['pic']['url'], 'letter': c['pic']['letter'],
             'hue': c['pic']['hue'], 'room': c['pic']['room']} for c in _chat_choices(request.user, saved=False) if c['can_post']]
    return JsonResponse({'items': rows})


@login_required
@module_required('chat')
@require_POST
def forward(request):
    try:
        sent = services.forward_messages(request.user, request.POST.getlist('ids'), request.POST.getlist('to'),
                                         hide_sender=request.POST.get('hide') == '1')
    except ChatError as exc:
        return JsonResponse({'error': exc.message}, status=exc.status)
    return JsonResponse({'ok': True, 'count': len(sent), 'thread': request.POST.getlist('to')[0] if sent else None})


@login_required
@module_required('chat')
def search(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    if not services.can_read(thread, request.user):
        raise Http404
    found = services.search_messages(thread, request.user, request.GET.get('q', ''))
    return JsonResponse({'items': [{'id': m.pk, 'name': m.sender.get_display_name(), 'text': m.body[:160],
                                    'time': message_payload(m)['created_at']} for m in found]})


@login_required
@module_required('chat')
def saved(request):
    """«Избранное» — чат с самим собой."""
    return redirect('chat:thread', pk=services.open_saved(request.user).pk)


@login_required
@module_required('chat')
def post(request, pk, msg_id):
    """Комментарии под постом канала."""
    thread = get_object_or_404(Thread, pk=pk)
    if not services.can_read(thread, request.user):
        raise Http404
    try:
        if request.method == 'POST':
            services.add_comment(request.user, msg_id, request.POST.get('body', ''), request.POST.get('reply_to'))
            return redirect('chat:post', pk=pk, msg_id=msg_id)
        data = services.comments_of(request.user, msg_id)
    except ChatError as exc:
        messages.error(request, exc.message)
        return redirect('chat:thread', pk=pk)
    if data['post'].thread_id != thread.pk:
        raise Http404
    rows = [data['post'], *data['items']]
    decorate(rows, request.user)
    for m in data['items']:
        m.hue = m.sender_id % 7
    return render(request, 'chat/post.html', {
        'thread': thread, 'post': data['post'], 'items': data['items'], 'member': rooms.membership(thread, request.user),
        'active_section': 'chat'})


def by_handle(request, handle):
    """/@имя/ — человек, группа или канал с таким именем (упоминания в сообщениях ведут сюда)."""
    handle = handle.lower()
    user = User.objects.filter(handle=handle, is_active=True).first()
    if user is not None:
        return redirect('accounts:public', pk=user.pk)
    room = rooms.by_handle(handle)
    if room is not None and room.is_public:
        return redirect('channel_public', handle=handle)
    raise Http404


@login_required
@module_required('chat')
def find(request):
    """Единый поиск из строки над чатами: люди, каналы и группы, сообщества, сообщения (JSON)."""
    from django.urls import reverse

    from . import finder
    from .views_rooms import pic
    from .views_spaces import space_pic
    data = finder.find(request.user, request.GET.get('q', ''))

    def face(p):
        return {'url': p['url'], 'letter': p['letter'], 'hue': p['hue']}
    people_rows = [{'name': u.get_display_name(), 'sub': f'@{u.handle}' if u.handle else '', 'href': f"{reverse('chat:start')}?user={u.pk}",
                    'pic': {'url': u.avatar.url if u.avatar else '', 'letter': (u.get_display_name() or '?')[:1].upper(), 'hue': u.pk % 7}}
                   for u in data['people']]
    room_rows = [{'name': t.title, 'sub': (str(_('канал')) if t.is_channel else str(_('группа'))) + f' · {t.members_count}',
                  'href': reverse('chat:thread', args=[t.pk]), 'pic': face(pic(t)), 'verified': t.platform_verified} for t in data['rooms']]
    space_rows = [{'name': s.title, 'sub': f"{_('сообщество')} · {s.members_count}", 'href': reverse('spaces:space', args=[s.pk]),
                   'pic': face(space_pic(s)), 'verified': s.platform_verified} for s in data['spaces']]
    msg_rows = [{'name': m['title'] or str(_('Избранное')), 'sub': (m['who'] + ': ' if m['who'] else '') + m['text'], 'time': m['time'],
                 'href': f"{reverse('chat:thread', args=[m['thread']])}?at={m['id']}"} for m in data['messages']]
    return JsonResponse({'global': people_rows + room_rows + space_rows, 'messages': msg_rows})
