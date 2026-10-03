"""Сообщества на сайте (как Discord): список и каталог, создание, страница сообщества с каналами, управление."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.decorators import module_required

from . import spaces
from .models import Space, SpaceMember, SpaceRole, SpaceTask
from .rooms import ChatError

User = get_user_model()


def space_pic(space) -> dict:
    return {'url': space.icon.url if space.icon else '', 'letter': (space.title[:1] or '#').upper(), 'hue': space.pk % 7, 'name': space.title,
            'room': 'group', 'verified': space.platform_verified, 'online': False}


def side(space, user, current=None) -> dict:
    """Боковые панели сообщества для страницы чата: мои сообщества (полоска слева), каналы и участники по ролям (справа)."""
    data = spaces.tree(space, user)
    return {**data, 'pic': space_pic(space), 'current': current, 'roster': spaces.roster(space, user),
            'rail': [{'id': s.pk, 'pic': space_pic(s), 'on': s.pk == space.pk} for s in spaces.mine(user)]}


@module_required('communities')
def index(request):
    q = request.GET.get('q', '')
    mine = spaces.mine(request.user)
    mine_ids = {s.pk for s in mine}
    return render(request, 'chat/spaces.html', {
        'mine': [{'space': s, 'pic': space_pic(s)} for s in mine], 'q': q,
        'catalog': [{'space': s, 'pic': space_pic(s), 'member': s.pk in mine_ids} for s in spaces.catalog(q)[:60]],
        'active_section': 'communities'})


@login_required
@module_required('communities')
def new(request):
    data = {'title': '', 'about': '', 'is_public': True}
    if request.method == 'POST':
        data = {'title': request.POST.get('title', ''), 'about': request.POST.get('about', ''), 'is_public': bool(request.POST.get('is_public'))}
        try:
            space = spaces.create(request.user, data['title'], data['about'], data['is_public'], request.FILES.get('icon'))
            return redirect('spaces:space', pk=space.pk)
        except ChatError as exc:
            messages.error(request, exc.message)
    return render(request, 'chat/space_new.html', {'data': data, 'active_section': 'communities'})


def _space(request, pk):
    obj = get_object_or_404(Space, pk=pk)
    if not spaces.can_view(obj, request.user):
        raise Http404
    return obj


@module_required('communities')
def space(request, pk):
    obj = get_object_or_404(Space, pk=pk)
    if not spaces.can_view(obj, request.user):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        raise Http404
    data = spaces.tree(obj, request.user)
    me, perms = data['me'], data['perms']
    manage = 'manage_space' in perms
    base = request.build_absolute_uri('/communities/join/')
    return render(request, 'chat/space.html', {
        **data, 'pic': space_pic(obj), 'people': spaces.people(obj, 80) if me else [],
        'invite': f'{base}{obj.invite_code}/' if manage else '',
        'invites': [{'obj': i, 'link': f'{base}{i.code}/'} for i in obj.invites.all()[:20]] if manage else [],
        'space_roles': list(obj.roles.all()) if me else [], 'perm_choices': SpaceRole.PERMS,
        'banned': spaces.banned(obj) if 'kick' in perms else [],
        'logs': list(obj.logs.select_related('actor')[:40]) if manage else [],
        'threads_all': list(obj.threads.order_by('space_order', 'pk')) if 'manage_channels' in perms else [],
        'ranks': [r for r in SpaceMember.ROLES if r[0] in ('admin', 'mod', 'member')], 'timeouts': list(spaces.TIMEOUTS),
        'active_section': 'communities'})


@login_required
@module_required('communities')
def board(request, pk):
    """Доска задач сообщества: идеи → делаем → готово."""
    obj = _space(request, pk)
    me = spaces.membership(obj, request.user)
    if me is None:
        return redirect('spaces:space', pk=obj.pk)
    if request.method == 'POST':
        a, p = request.POST.get('action', ''), request.POST
        try:
            if a == 'save':
                spaces.save_task(obj, request.user, p.get('task') or None, p.get('title', ''), p.get('note', ''), p.get('assignee', ''), p.get('due', ''))
            elif a == 'move':
                spaces.move_task(obj, request.user, p.get('task'), p.get('status', ''))
            elif a == 'delete':
                spaces.delete_task(obj, request.user, p.get('task'))
        except ChatError as exc:
            messages.error(request, exc.message)
        return redirect('spaces:board', pk=obj.pk)
    cols = spaces.tasks(obj, request.user)
    return render(request, 'chat/space_board.html', {
        'space': obj, 'pic': space_pic(obj), 'me': me, 'people': spaces.people(obj, 100),
        'columns': [{'key': k, 'title': n, 'tasks': cols[k]} for k, n in SpaceTask.STATUSES],
        'manage': spaces.can(obj, request.user, 'manage_tasks'), 'active_section': 'communities'})


@login_required
@module_required('communities')
def voice_room(request, pk, voice_id):
    """Голосовая комната: звук идёт напрямую между участниками (до нескольких человек)."""
    from . import voice
    obj = _space(request, pk)
    room = get_object_or_404(obj.voices, pk=voice_id)
    if spaces.membership(obj, request.user) is None:
        return redirect('spaces:space', pk=obj.pk)
    return render(request, 'chat/space_voice.html', {'space': obj, 'room': room, 'pic': space_pic(obj), 'max': voice.MAX_PEERS,
                                                     'me_id': request.user.pk, 'active_section': 'communities'})


@login_required
@module_required('communities')
def join(request, code):
    obj = spaces.by_code(code)
    if obj is None:
        raise Http404
    try:
        spaces.join(obj, request.user, code)
    except ChatError as exc:
        messages.error(request, exc.message)
        return redirect('spaces:index')
    return redirect('spaces:space', pk=obj.pk)


@login_required
@module_required('communities')
@require_POST
def act(request, pk):
    obj = get_object_or_404(Space, pk=pk)
    a, p, user = request.POST.get('action', ''), request.POST, request.user
    try:
        if a == 'join':
            spaces.join(obj, user)
        elif a == 'leave':
            spaces.leave(obj, user)
            return redirect('spaces:index')
        elif a == 'delete':
            spaces.delete(obj, user)
            return redirect('spaces:index')
        elif a == 'nick':
            spaces.set_nick(obj, user, p.get('nick', ''))
        elif a == 'update':
            spaces.update(obj, user, {'title': p.get('title', ''), 'about': p.get('about', ''), 'is_public': p.get('is_public', '')}, request.FILES.get('icon'))
        elif a == 'invite':
            spaces.reset_invite(obj, user)
        elif a == 'category':
            spaces.add_category(obj, user, p.get('title', ''))
        elif a == 'channel':
            spaces.add_channel(obj, user, p.get('title', ''), p.get('kind', 'text'), p.get('category') or None,
                               private=bool(p.get('private')), role_ids=p.getlist('roles'))
        elif a == 'rename':
            spaces.rename_channel(obj, user, p.get('thread'), p.get('title', ''))
        elif a == 'drop_channel':
            spaces.delete_channel(obj, user, thread_id=p.get('thread') or None, voice_id=p.get('voice') or None)
        elif a == 'drop_category':
            spaces.delete_category(obj, user, p.get('category'))
        elif a in ('role', 'kick', 'timeout', 'unban', 'member_roles'):
            target = get_object_or_404(User, pk=p.get('user'))
            if a == 'kick':
                spaces.kick(obj, user, target)
            elif a == 'timeout':
                spaces.timeout(obj, user, target, p.get('for', ''))
            elif a == 'unban':
                spaces.unban(obj, user, target)
            elif a == 'member_roles':
                spaces.set_member_roles(obj, user, target, p.getlist('roles'))
            else:
                spaces.set_role(obj, user, target, p.get('role', 'member'))
        elif a == 'role_save':
            spaces.save_role(obj, user, p.get('role_id') or None, p.get('name', ''), p.get('color', ''), p.getlist('perms'), bool(p.get('hoist')))
        elif a == 'role_delete':
            spaces.delete_role(obj, user, p.get('role_id'))
        elif a == 'channel_set':
            spaces.set_channel(obj, user, p.get('thread'), title=p.get('title'), topic=p.get('topic', ''),
                               private=bool(p.get('private')), role_ids=p.getlist('roles'))
        elif a == 'invite_new':
            spaces.create_invite(obj, user, p.get('hours') or 0, p.get('max_uses') or 0)
        elif a == 'invite_delete':
            spaces.delete_invite(obj, user, p.get('invite'))
        else:
            raise Http404
        if a in ('nick', 'update', 'category', 'channel', 'rename', 'role_save', 'channel_set', 'member_roles', 'invite_new'):
            messages.success(request, _('Сохранено.'))
    except ChatError as exc:
        messages.error(request, exc.message)
    return redirect('spaces:space', pk=obj.pk)
