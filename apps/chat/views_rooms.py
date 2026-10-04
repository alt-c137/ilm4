"""Страницы групп и каналов: создание, каталог, сведения и участники, вступление по ссылке."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.decorators import module_required

from . import rooms, services
from .models import Member, Thread
from .services import ChatError

User = get_user_model()


def pic(thread, other=None, viewer=None) -> dict:
    """Аватар для списка и шапки: у группы / канала — свой, у личного диалога — собеседника."""
    if thread.is_room:
        return {'url': thread.avatar.url if thread.avatar else '', 'letter': (thread.title[:1] or '#').upper(),
                'hue': thread.pk % 7, 'name': thread.title, 'room': thread.kind, 'verified': thread.platform_verified,
                'online': False}
    if thread.is_saved:                          # «Избранное» — чат с самим собой
        return {'url': '', 'letter': '', 'hue': 2, 'name': str(_('Избранное')), 'room': '', 'verified': False,
                'online': False, 'saved': True}
    from apps.accounts import people

    from . import persona
    masked = persona.mask(thread, other)
    if masked:                                   # чат никяха: имя из анкеты, без аватара, «в сети» и ссылки на основной профиль
        return {'url': masked.get('avatar', ''), 'letter': masked['name'][:1].upper(), 'hue': thread.pk % 7, 'name': masked['name'],
                'room': '', 'verified': False, 'online': False, 'masked': True, 'link': masked['link'], 'board': masked.get('kind') == 'board'}
    name = people.shown_name(other, viewer)                # как человек записан у меня в контактах — как в Telegram
    return {'url': other.avatar.url if other and other.avatar else '', 'letter': name[:1].upper(),
            'hue': (other.pk if other else 0) % 7, 'name': name, 'room': '',
            'verified': bool(other and other.platform_verified),
            'online': bool(other and viewer is not None and people.quick_online(other, viewer))}


def _room(pk) -> Thread:
    thread = get_object_or_404(Thread, pk=pk)
    if not thread.is_room or not rooms.enabled(thread.kind):
        raise Http404
    return thread


def _fail(request, exc, to='chat:inbox', **kwargs):
    messages.error(request, exc.message)
    return redirect(to, **kwargs)


@login_required
@module_required('chat')
def room_new(request):
    """Новая группа или канал."""
    kind = request.POST.get('kind') or request.GET.get('kind') or Thread.GROUP
    if kind not in (Thread.GROUP, Thread.CHANNEL):
        kind = Thread.GROUP
    allowed = {k: rooms.can_create(request.user, k) for k in (Thread.GROUP, Thread.CHANNEL)}
    if not any(allowed.values()):
        raise Http404
    if not allowed[kind]:
        kind = next(k for k, ok in allowed.items() if ok)
    data = request.POST if request.method == 'POST' else {}
    if request.method == 'POST':
        try:
            thread = rooms.create(request.user, kind, data.get('title', ''), data.get('about', ''),
                                  is_public=data.get('is_public') == 'on', handle=data.get('handle', ''),
                                  avatar=request.FILES.get('avatar'))
        except ChatError as exc:
            messages.error(request, exc.message)
        else:
            return redirect('chat:thread', pk=thread.pk)
    return render(request, 'chat/room_new.html', {'kind': kind, 'allowed': allowed, 'data': data,
                                                  **_side(request)})


def _side(request):
    from .views import _side as side
    return side(request)


@login_required
@module_required('chat')
def channels(request):
    """Каталог публичных каналов и групп."""
    kind, q = request.GET.get('kind', ''), request.GET.get('q', '')
    page = Paginator(rooms.catalog(q, kind), 30).get_page(request.GET.get('page'))
    mine = set(Thread.objects.filter(pk__in=[t.pk for t in page], participants=request.user).values_list('pk', flat=True))
    return render(request, 'chat/channels.html', {
        'page': page, 'q': q, 'kind': kind, 'mine': mine, 'cards': [(t, pic(t)) for t in page],
        'can_group': rooms.can_create(request.user, Thread.GROUP),
        'can_channel': rooms.can_create(request.user, Thread.CHANNEL), **_side(request)})


def public_page(request, handle):
    """Адрес канала для всех: ilm4.com/c/имя/ — им делятся в соцсетях и на визитках."""
    from apps.core.models import ModuleConfig
    thread = rooms.by_handle(handle)
    if thread is None or not thread.is_public or not rooms.enabled(thread.kind) \
            or not ModuleConfig.objects.filter(key='chat', status=ModuleConfig.ON).exists():
        raise Http404
    if request.user.is_authenticated:
        return redirect('chat:thread', pk=thread.pk)
    return render(request, 'chat/room_public.html', {'room': thread, 'pic': pic(thread)})


@login_required
@module_required('chat')
def room_info(request, pk):
    """Сведения о группе / канале: описание, участники, приглашение, настройки."""
    thread = _room(pk)
    if not services.can_read(thread, request.user):
        return redirect('chat:inbox')
    info = rooms.info(thread, request.user)
    if request.method == 'POST':
        try:
            rooms.update(thread, request.user, {
                'title': request.POST.get('title', thread.title), 'about': request.POST.get('about', ''),
                'is_public': request.POST.get('is_public', ''), 'handle': request.POST.get('handle', ''),
                'only_admins_post': request.POST.get('only_admins_post', ''),
                'protected': request.POST.get('protected', ''), 'reactions_on': request.POST.get('reactions_on', ''),
                'comments_on': request.POST.get('comments_on', ''),
                'slow_seconds': request.POST.get('slow_seconds', '0')}, avatar=request.FILES.get('avatar'))
            messages.success(request, _('Сохранено.'))
        except ChatError as exc:
            messages.error(request, exc.message)
        return redirect('chat:room_info', pk=pk)
    people = rooms.members(thread) if info['member'] and (thread.kind == Thread.GROUP or info['admin']) else []
    for m in people:
        m.hue = m.user_id % 7
    addable = []
    if info['admin']:
        inside = set(thread.participants.values_list('pk', flat=True))
        known = (User.objects.filter(chat_threads__kind=Thread.DIRECT, chat_threads__participants=request.user, is_active=True)
                 .exclude(pk__in=inside).distinct()[:100])
        addable = list(known)
    link = request.build_absolute_uri(f'/chat/join/{thread.invite_code}/') if info['invite'] else ''
    public_link = request.build_absolute_uri(f'/c/{thread.handle}/') if thread.is_public and thread.handle else ''
    return render(request, 'chat/room_info.html', {
        'room_photos': [{'url': thread.avatar.url, 'name': thread.title}] if thread.avatar else [],
        'thread': thread, 'room': thread, 'info': info, 'pic': pic(thread), 'people': people, 'addable': addable,
        'invite_link': link, 'public_link': public_link, 'me_owner': info['role'] == Member.OWNER,
        'can_moderate': request.user.is_staff and request.user.has_perm('chat.change_thread'), **_side(request)})


@login_required
@module_required('chat')
def room_join_link(request, code):
    """Ссылка-приглашение: показать, куда зовут, и вступить."""
    thread = rooms.by_code(code)
    if thread is None or not rooms.enabled(thread.kind):
        raise Http404
    if services.is_participant(thread, request.user):
        return redirect('chat:thread', pk=thread.pk)
    if request.method == 'POST':
        try:
            rooms.join(thread, request.user, code)
        except ChatError as exc:
            return _fail(request, exc)
        return redirect('chat:thread', pk=thread.pk)
    return render(request, 'chat/room_public.html', {'room': thread, 'pic': pic(thread), 'code': code})


@login_required
@module_required('chat')
@require_POST
def room_act(request, pk, action):
    """Действия участника: вступить, выйти, звук, новая ссылка, добавить людей, удалить чат."""
    thread = _room(pk)
    user = request.user
    try:
        if action == 'join':
            rooms.join(thread, user, request.POST.get('code', ''))
        elif action == 'leave':
            rooms.leave(thread, user)
            messages.info(request, _('Вы вышли.'))
            return redirect('chat:inbox')
        elif action in ('mute', 'unmute'):
            rooms.set_muted(thread, user, action == 'mute')
        elif action == 'invite':
            rooms.reset_invite(thread, user)
            messages.success(request, _('Ссылка обновлена — старая больше не работает.'))
            return redirect('chat:room_info', pk=pk)
        elif action == 'add':
            ids = [int(x) for x in request.POST.getlist('users') if x.isdigit()]
            n = rooms.add_members(thread, user, User.objects.filter(pk__in=ids))
            messages.success(request, _('Добавлено: {n}').format(n=n))
            return redirect('chat:room_info', pk=pk)
        elif action == 'delete':
            rooms.delete(thread, user)
            messages.info(request, _('Удалено.'))
            return redirect('chat:inbox')
        elif action in ('close', 'open', 'verify', 'unverify'):
            if not (user.is_staff and user.has_perm('chat.change_thread')):
                raise Http404
            from apps.accounts.audit import log_action
            if action in ('close', 'open'):
                thread.closed = action == 'close'
                thread.save(update_fields=['closed'])
            else:
                thread.platform_verified = action == 'verify'
                thread.save(update_fields=['platform_verified'])
            log_action(request, f'Группа/канал: {action}', f'#{thread.pk} {thread.title}'[:200])
            return redirect('chat:room_info', pk=pk)
        else:
            raise Http404
    except ChatError as exc:
        return _fail(request, exc)
    return redirect(request.POST.get('next') or 'chat:thread', **({} if request.POST.get('next') else {'pk': pk}))


@login_required
@module_required('chat')
@require_POST
def room_member(request, pk, user_id, action):
    """Владелец и админы: назначить / снять админа, удалить участника."""
    thread = _room(pk)
    target = get_object_or_404(User, pk=user_id)
    try:
        if action == 'remove':
            rooms.remove_member(thread, request.user, target)
        elif action in ('admin', 'unadmin'):
            rooms.set_admin(thread, request.user, target, action == 'admin')
        else:
            raise Http404
    except ChatError as exc:
        messages.error(request, exc.message)
    return redirect('chat:room_info', pk=pk)
