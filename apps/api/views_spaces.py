"""API сообществ (как Discord) для приложения: список и каталог, создание, каналы, роли, свой ник."""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.chat import spaces
from apps.chat.models import Space, SpaceMember, SpaceRole
from apps.chat.rooms import ChatError

from .base import ApiError, abs_url, api, file_url

User = get_user_model()


def _card(request, s, member=False) -> dict:
    return {'id': s.pk, 'title': s.title, 'about': s.about, 'icon': file_url(request, s.icon), 'members': s.members_count,
            'public': s.is_public, 'verified': s.platform_verified, 'member': member}


def _wrap(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc


def _full(request, s) -> dict:
    data = spaces.tree(s, request.user)
    me, perms = data['me'], data['perms']
    manage = 'manage_space' in perms
    return {**_card(request, s, member=me is not None), 'groups': data['groups'], 'unread': data['unread'],
            'me': {'role': me.role, 'nick': me.nick, 'admin': me.is_admin, 'mod': me.can_moderate, 'perms': sorted(perms)} if me else None,
            'invite': abs_url(request, f'/communities/join/{s.invite_code}/') if manage else '',
            'board': abs_url(request, f'/communities/{s.pk}/board/'), 'web': abs_url(request, f'/communities/{s.pk}/'),
            'space_roles': [{'id': r.pk, 'name': r.name, 'color': r.color, 'perms': r.perms} for r in s.roles.all()] if me else [],
            'people': [{'id': m.user_id, 'name': m.nick or m.user.get_display_name(), 'real': m.user.get_display_name() if m.nick else '',
                        'avatar': abs_url(request, spaces.avatar_of(m.user)) if spaces.avatar_of(m.user) else '', 'role': m.role, 'role_name': str(m.get_role_display()),
                        'roles': [{'id': r.pk, 'name': r.name, 'color': r.color} for r in m.roles.all()],
                        'timeout': bool(m.muted_until and m.muted_until > timezone.now())}
                       for m in spaces.people(s, 100)] if me else [],
            'roles': [{'key': k, 'name': str(n)} for k, n in SpaceMember.ROLES if k in ('admin', 'mod', 'member')],
            'manage': _manage(request, s, perms) if me else None}


def _manage(request, s, perms) -> dict | None:
    """Данные для экрана «Управление сообществом» — только то, на что у человека есть права."""
    if not perms & {'manage_space', 'manage_roles', 'manage_channels', 'kick'}:
        return None
    out = {'perm_choices': [{'key': k, 'name': str(n)} for k, n in SpaceRole.PERMS]}
    if 'manage_channels' in perms:
        out['channels'] = [{'id': t.pk, 'title': t.title, 'topic': t.space_topic, 'private': t.space_private,
                            'roles': list(t.space_roles_allowed.values_list('pk', flat=True))}
                           for t in s.threads.order_by('space_order', 'pk')]
    if 'manage_space' in perms:
        out['invites'] = [{'id': i.pk, 'link': abs_url(request, f'/communities/join/{i.code}/'), 'uses': i.uses, 'max_uses': i.max_uses,
                           'expires': i.expires_at.isoformat() if i.expires_at else ''} for i in s.invites.all()[:20]]
        out['logs'] = [{'time': timezone.localtime(x.created_at).strftime('%d.%m %H:%M'), 'actor': x.actor.get_display_name() if x.actor else '',
                        'action': x.action, 'text': x.text} for x in s.logs.select_related('actor')[:40]]
    if 'kick' in perms:
        out['banned'] = [{'id': b.user_id, 'name': b.user.get_display_name()} for b in spaces.banned(s)]
    return out


@api(auth=True, module='communities')
def index(request):
    """Мои сообщества и каталог открытых (?q= — поиск)."""
    mine = spaces.mine(request.user)
    ids = {s.pk for s in mine}
    return {'mine': [_card(request, s, True) for s in mine],
            'catalog': [_card(request, s, s.pk in ids) for s in spaces.catalog(request.GET.get('q', ''))[:60]]}


@api(methods=('POST',), auth=True, module='communities')
def new(request):
    d = request.data
    s = _wrap(spaces.create, request.user, str(d.get('title', '')), str(d.get('about', '')),
              str(d.get('is_public', '')).lower() in ('1', 'true', 'on'), request.FILES.get('icon'))
    return {'id': s.pk}


@api(methods=('POST',), auth=True, module='communities')
def join(request, code):
    s = spaces.by_code(code)
    if s is None:
        raise ApiError('Не найдено', 404)
    _wrap(spaces.join, s, request.user, code)
    return {'id': s.pk}


@api(auth=True, module='communities')
def detail(request, pk):
    s = get_object_or_404(Space, pk=pk)
    if not spaces.can_view(s, request.user):
        raise ApiError('Не найдено', 404)
    return _full(request, s)


@api(methods=('POST',), auth=True, module='communities')
def act(request, pk):
    """{action: join | leave | delete | nick {nick} | update {title, about, is_public} | invite | category {title} |
    channel {title, kind, category} | rename {thread, title} | drop_channel {thread | voice} | drop_category {category} |
    role {user, role} | kick {user}}"""
    s = get_object_or_404(Space, pk=pk)
    d, user = request.data, request.user
    a = str(d.get('action', ''))
    if a == 'join':
        _wrap(spaces.join, s, user)
    elif a == 'leave':
        _wrap(spaces.leave, s, user)
        return {'ok': True, 'gone': True}
    elif a == 'delete':
        _wrap(spaces.delete, s, user)
        return {'ok': True, 'gone': True}
    elif a == 'nick':
        _wrap(spaces.set_nick, s, user, str(d.get('nick', '')))
    elif a == 'update':
        _wrap(spaces.update, s, user, {k: d.get(k) for k in ('title', 'about', 'is_public') if k in d}, request.FILES.get('icon'))
    elif a == 'invite':
        _wrap(spaces.reset_invite, s, user)
    elif a == 'category':
        _wrap(spaces.add_category, s, user, str(d.get('title', '')))
    elif a == 'channel':
        _wrap(spaces.add_channel, s, user, str(d.get('title', '')), str(d.get('kind', 'text')), d.get('category') or None,
              private=bool(d.get('private')), role_ids=d.get('roles') or [])
    elif a == 'rename':
        _wrap(spaces.rename_channel, s, user, d.get('thread'), str(d.get('title', '')))
    elif a == 'drop_channel':
        _wrap(spaces.delete_channel, s, user, thread_id=d.get('thread') or None, voice_id=d.get('voice') or None)
    elif a == 'drop_category':
        _wrap(spaces.delete_category, s, user, d.get('category'))
    elif a in ('role', 'kick', 'timeout', 'unban', 'member_roles'):
        target = get_object_or_404(User, pk=d.get('user'))
        if a == 'kick':
            _wrap(spaces.kick, s, user, target)
        elif a == 'timeout':
            _wrap(spaces.timeout, s, user, target, str(d.get('for', '')))
        elif a == 'unban':
            _wrap(spaces.unban, s, user, target)
        elif a == 'member_roles':
            _wrap(spaces.set_member_roles, s, user, target, d.get('roles') or [])
        else:
            _wrap(spaces.set_role, s, user, target, str(d.get('role', 'member')))
    elif a == 'role_save':
        _wrap(spaces.save_role, s, user, d.get('role_id') or None, str(d.get('name', '')), str(d.get('color', '')), d.get('perms') or [], bool(d.get('hoist', True)))
    elif a == 'role_delete':
        _wrap(spaces.delete_role, s, user, d.get('role_id'))
    elif a == 'channel_set':
        _wrap(spaces.set_channel, s, user, d.get('thread'), title=d.get('title'), topic=d.get('topic'),
              private=d.get('private'), role_ids=d.get('roles'))
    elif a == 'invite_delete':
        _wrap(spaces.delete_invite, s, user, d.get('invite'))
    elif a == 'invite_new':
        inv = _wrap(spaces.create_invite, s, user, d.get('hours') or 0, d.get('max_uses') or 0)
        return {**_full(request, s), 'new_invite': abs_url(request, f'/communities/join/{inv.code}/')}
    else:
        raise ApiError('Неизвестное действие', 400)
    s.refresh_from_db()
    return _full(request, s)


@api(methods=('GET', 'POST'), auth=True, module='communities')
def board(request, pk):
    """Доска задач: GET — колонки; POST {action: save {task?, title, note, assignee, due} | move {task, status} | delete {task}}."""
    s = get_object_or_404(Space, pk=pk)
    if spaces.membership(s, request.user) is None:
        raise ApiError('Не найдено', 404)
    if request.method == 'POST':
        d = request.data
        a = str(d.get('action', ''))
        if a == 'save':
            _wrap(spaces.save_task, s, request.user, d.get('task') or None, str(d.get('title', '')), str(d.get('note', '')), d.get('assignee'), d.get('due'))
        elif a == 'move':
            _wrap(spaces.move_task, s, request.user, d.get('task'), str(d.get('status', '')))
        elif a == 'delete':
            _wrap(spaces.delete_task, s, request.user, d.get('task'))
    cols = _wrap(spaces.tasks, s, request.user)
    manage = spaces.can(s, request.user, 'manage_tasks')
    from apps.chat.models import SpaceTask
    return {'title': s.title, 'columns': [{'key': k, 'title': str(n), 'tasks': [
        {'id': t.pk, 'title': t.title, 'note': t.note, 'assignee': t.assignee.get_display_name() if t.assignee else '',
         'due': t.due.isoformat() if t.due else '', 'mine': manage or request.user.pk in (t.creator_id, t.assignee_id)} for t in cols[k]]}
        for k, n in SpaceTask.STATUSES]}
