"""Сообщества — как серверы в Discord: категории и каналы, свои роли с цветом и правами, закрытые каналы,
голосовые комнаты, приглашения со сроком, тайм-ауты, журнал действий, доска задач.

Образец возможностей — Discord и открыто описанные функции похожих проектов; код свой.

Устройство:
* Space → категории (SpaceCategory) → каналы. Текстовый канал и канал объявлений — обычные чаты (Thread с полем space):
  в них работает всё, что есть в чатах. Голосовая комната — SpaceVoice (звук идёт напрямую между участниками,
  см. apps/chat/voice.py; для больших комнат нужен медиасервер LiveKit).
* Права: владелец — всё; «админ» — всё, кроме удаления сообщества; «модератор» — удалять сообщения, тайм-аут, удалять
  участников; плюс права из своих ролей (SpaceRole.perms). Проверка — can(space, user, 'право').
* Доступ к каналу держится на том же, что у групп: человек — участник чата-канала (Member). Открытый канал получают
  все участники сообщества, закрытый (space_private) — только те, у кого есть роль из списка канала, и админы.
  Любое изменение ролей и каналов пересобирает доступ (_sync_member / _sync_thread).
* В общий список чатов каналы не попадают (services.inbox берёт чаты без space). Уведомления из каналов — только при
  @упоминании, @everyone, @роль и ответе (Member.muted=True).

Точка входа для страниц и API — функции этого файла.
"""
import re
import secrets
from datetime import date, timedelta

from django.core.cache import cache
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import (
    Member,
    Space,
    SpaceCategory,
    SpaceInvite,
    SpaceLog,
    SpaceMember,
    SpaceRole,
    SpaceTask,
    SpaceVoice,
    Thread,
)
from .rooms import ChatError, _avatar

MAX_OWNED = 5                 # сообществ у одного владельца
MAX_CHANNELS = 60
MAX_CATEGORIES = 20
MAX_ROLES = 30
MAX_TASKS = 500
TEXT, NEWS, VOICE = 'text', 'news', 'voice'
ALL_PERMS = [k for k, _n in SpaceRole.PERMS]
MOD_PERMS = {'kick', 'timeout', 'delete_messages'}
TIMEOUTS = {'5m': 300, '1h': 3600, '1d': 86400, '7d': 7 * 86400}
RANK = {SpaceMember.OWNER: 3, SpaceMember.ADMIN: 2, SpaceMember.MOD: 1, SpaceMember.MEMBER: 0}
COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def enabled() -> bool:
    from apps.core.models import ModuleConfig
    return ModuleConfig.objects.filter(key='communities', status='on').exists()


def membership(space, user):
    if not getattr(user, 'is_authenticated', False):
        return None
    return SpaceMember.objects.filter(space=space, user=user).exclude(role=SpaceMember.BANNED).first()


def perms_of(member) -> set:
    """Права участника: по основной роли и по своим ролям сообщества."""
    if member is None:
        return set()
    if member.role in (SpaceMember.OWNER, SpaceMember.ADMIN):
        return set(ALL_PERMS)
    out = set(MOD_PERMS) if member.role == SpaceMember.MOD else set()
    for role in member.roles.all():
        out.update(p for p in role.perms if p in ALL_PERMS)
    return out


def can(space, user, perm: str) -> bool:
    return perm in perms_of(membership(space, user))


def _need(space, user, perm: str = '') -> SpaceMember:
    m = membership(space, user)
    if m is None:
        raise ChatError(_('Вы не в этом сообществе.'), 403)
    if perm and perm not in perms_of(m):
        raise ChatError(_('На это у вас нет прав в сообществе.'), 403)
    return m


def can_view(space, user) -> bool:
    if space.closed:
        return bool(getattr(user, 'is_staff', False))
    return space.is_public or membership(space, user) is not None


def _log(space, actor, action: str, text: str = '') -> None:
    SpaceLog.objects.create(space=space, actor=actor, action=action, text=text[:200])


# ---------- доступ к каналам ----------

def _thread_role(member) -> str:
    """Роль в чате-канале: кто может удалять и закреплять сообщения — админ чата."""
    if member.role == SpaceMember.OWNER:
        return Member.OWNER
    return Member.ADMIN if 'delete_messages' in perms_of(member) else Member.MEMBER


def _sees(member, thread, allowed_roles=None) -> bool:
    if not thread.space_private or member.role in (SpaceMember.OWNER, SpaceMember.ADMIN):
        return True
    allowed = allowed_roles if allowed_roles is not None else set(thread.space_roles_allowed.values_list('pk', flat=True))
    return bool(allowed & set(member.roles.values_list('pk', flat=True)))


def _grant(thread, member) -> None:
    role = _thread_role(member)
    Member.objects.update_or_create(thread=thread, user_id=member.user_id, defaults={'role': role},
                                    create_defaults={'role': role, 'muted': True, 'last_read_at': timezone.now()})
    thread.participants.add(member.user_id)


def _revoke(thread, user_id) -> None:
    Member.objects.filter(thread=thread, user_id=user_id).delete()
    thread.participants.remove(user_id)


def _sync_member(space, member) -> None:
    """Привести доступ участника к каналам в соответствие с его ролями."""
    for thread in space.threads.all():
        if _sees(member, thread):
            _grant(thread, member)
        else:
            _revoke(thread, member.user_id)
    cache.delete(f'chat:nick:{space.pk}:{member.user_id}')


def _sync_thread(thread) -> None:
    """Привести состав канала в соответствие с его закрытостью и ролями."""
    allowed = set(thread.space_roles_allowed.values_list('pk', flat=True))
    keep = set()
    for member in thread.space.members.exclude(role=SpaceMember.BANNED).prefetch_related('roles'):
        if _sees(member, thread, allowed):
            _grant(thread, member)
            keep.add(member.user_id)
    for uid in list(thread.participants.exclude(pk__in=keep).values_list('pk', flat=True)):
        _revoke(thread, uid)
    Thread.objects.filter(pk=thread.pk).update(members_count=len(keep))


def _recount(space) -> None:
    Space.objects.filter(pk=space.pk).update(members_count=space.members.exclude(role=SpaceMember.BANNED).count())
    for thread in space.threads.all():
        Thread.objects.filter(pk=thread.pk).update(members_count=thread.participants.count())


# ---------- создание и настройки ----------

def create(user, title: str, about: str = '', is_public: bool = False, icon=None) -> Space:
    from apps.accounts import phone_verify
    if not enabled():
        raise ChatError(_('Сообщества сейчас выключены.'), 403)
    if phone_verify.needed(user, 'publish'):
        raise ChatError(_('Создавать сообщества можно только с подтверждённым номером.'), 403)
    title = (title or '').strip()[:80]
    if len(title) < 2:
        raise ChatError(_('Дайте название — хотя бы два знака.'))
    if Space.objects.filter(owner=user).count() >= MAX_OWNED and not user.is_staff:
        raise ChatError(_('У одного человека может быть не больше {n} сообществ.').format(n=MAX_OWNED), 409)
    with transaction.atomic():
        space = Space.objects.create(title=title, about=(about or '').strip()[:500], owner=user, is_public=bool(is_public),
                                     invite_code=secrets.token_urlsafe(12), icon=_avatar(icon) or '', members_count=1)
        SpaceMember.objects.create(space=space, user=user, role=SpaceMember.OWNER)
        info = SpaceCategory.objects.create(space=space, title=str(_('Информация')), order=0)
        talk = SpaceCategory.objects.create(space=space, title=str(_('Общение')), order=1)
        _channel(space, info, str(_('объявления')), NEWS, 0)
        _channel(space, talk, str(_('общий')), TEXT, 0)
        SpaceVoice.objects.create(space=space, category=talk, title=str(_('Голосовая')), order=1)
    return space


def _channel(space, category, title: str, kind: str, order: int, private: bool = False) -> Thread:
    thread = Thread.objects.create(kind=Thread.CHANNEL if kind == NEWS else Thread.GROUP, title=title[:120], owner=space.owner,
                                   invite_code=secrets.token_urlsafe(12), space=space, space_category=category, space_order=order,
                                   space_private=private)
    _sync_thread(thread)
    return thread


def update(space, user, data, icon=None) -> Space:
    _need(space, user, 'manage_space')
    if 'title' in data:
        title = str(data.get('title') or '').strip()[:80]
        if len(title) < 2:
            raise ChatError(_('Дайте название — хотя бы два знака.'))
        space.title = title
    if 'about' in data:
        space.about = str(data.get('about') or '').strip()[:500]
    if 'is_public' in data:
        space.is_public = str(data.get('is_public')).lower() in ('1', 'true', 'on')
    if icon:
        space.icon = _avatar(icon)
    space.save()
    _log(space, user, 'space', space.title)
    return space


def reset_invite(space, user) -> str:
    _need(space, user, 'manage_space')
    space.invite_code = secrets.token_urlsafe(12)
    space.save(update_fields=['invite_code'])
    _log(space, user, 'invite', str(_('новая постоянная ссылка')))
    return space.invite_code


def delete(space, user) -> None:
    m = membership(space, user)
    if not (m and m.role == SpaceMember.OWNER) and not user.is_staff:
        raise ChatError(_('Удалить может только владелец.'), 403)
    from . import rooms
    for thread in list(space.threads.all()):
        rooms.delete(thread, space.owner or user, from_space=True)
    space.delete()


# ---------- каналы и категории ----------

def add_category(space, user, title: str) -> SpaceCategory:
    _need(space, user, 'manage_channels')
    title = (title or '').strip()[:60]
    if not title:
        raise ChatError(_('Дайте категории название.'))
    if space.categories.count() >= MAX_CATEGORIES:
        raise ChatError(_('Слишком много категорий.'), 409)
    _log(space, user, 'category', title)
    return SpaceCategory.objects.create(space=space, title=title, order=space.categories.count())


def _role_ids(space, role_ids) -> list:
    return list(space.roles.filter(pk__in=[r for r in (role_ids or ()) if str(r).isdigit()]))


def add_channel(space, user, title: str, kind: str = TEXT, category_id=None, private: bool = False, role_ids=()):
    """Новый канал: text — пишут все, news — только админы, voice — голосовая комната. private — только выбранным ролям."""
    _need(space, user, 'manage_channels')
    title = (title or '').strip().lstrip('#')[:60]
    if len(title) < 2:
        raise ChatError(_('Дайте каналу название — хотя бы два знака.'))
    if kind not in (TEXT, NEWS, VOICE):
        raise ChatError(_('Неизвестный вид канала'))
    if space.threads.count() + space.voices.count() >= MAX_CHANNELS:
        raise ChatError(_('В сообществе уже максимум каналов.'), 409)
    category = space.categories.filter(pk=category_id).first() if category_id else space.categories.first()
    order = space.threads.filter(space_category=category).count() + space.voices.filter(category=category).count()
    _log(space, user, 'channel', f'+ {title}')
    if kind == VOICE:
        return SpaceVoice.objects.create(space=space, category=category, title=title, order=order)
    with transaction.atomic():
        thread = _channel(space, category, title, kind, order, private=bool(private))
        if private:
            thread.space_roles_allowed.set(_role_ids(space, role_ids))
            _sync_thread(thread)
    return thread


def set_channel(space, user, thread_id, title=None, topic=None, private=None, role_ids=None) -> None:
    """Настройки канала: название, тема, закрытый ли он и каким ролям открыт."""
    _need(space, user, 'manage_channels')
    thread = space.threads.filter(pk=thread_id).first()
    if thread is None:
        raise ChatError(_('Канал не найден'), 404)
    if title is not None:
        title = str(title).strip().lstrip('#')[:60]
        if len(title) < 2:
            raise ChatError(_('Дайте каналу название — хотя бы два знака.'))
        thread.title = title
    if topic is not None:
        thread.space_topic = str(topic).strip()[:200]
    if private is not None:
        thread.space_private = bool(private)
    thread.save()
    if role_ids is not None:
        thread.space_roles_allowed.set(_role_ids(space, role_ids))
    if private is not None or role_ids is not None:
        _sync_thread(thread)
    cache.delete(f'chat:ctx:{thread.pk}')
    _log(space, user, 'channel', f'~ {thread.title}')


def rename_channel(space, user, thread_id, title: str) -> None:
    set_channel(space, user, thread_id, title=title)


def delete_channel(space, user, thread_id=None, voice_id=None) -> None:
    _need(space, user, 'manage_channels')
    if voice_id:
        space.voices.filter(pk=voice_id).delete()
        return
    thread = space.threads.filter(pk=thread_id).first()
    if thread is None:
        return
    if space.threads.count() <= 1:
        raise ChatError(_('В сообществе должен остаться хотя бы один канал.'))
    _log(space, user, 'channel', f'− {thread.title}')
    from . import rooms
    rooms.delete(thread, space.owner or user, from_space=True)


def delete_category(space, user, category_id) -> None:
    """Категория удаляется, каналы остаются (без категории)."""
    _need(space, user, 'manage_channels')
    space.categories.filter(pk=category_id).delete()


# ---------- свои роли ----------

def save_role(space, user, role_id=None, name: str = '', color: str = '', perms=(), hoist: bool = True) -> SpaceRole:
    actor = _need(space, user, 'manage_roles')
    name = ' '.join((name or '').split())[:32]
    if len(name) < 2:
        raise ChatError(_('Дайте роли название.'))
    color = color if COLOR_RE.match(color or '') else '#6d5efc'
    wanted = [p for p in perms if p in ALL_PERMS]
    if not set(wanted) <= perms_of(actor):
        raise ChatError(_('Нельзя дать роли права, которых нет у вас.'), 403)
    role = space.roles.filter(pk=role_id).first() if role_id else None
    if role is None:
        if space.roles.count() >= MAX_ROLES:
            raise ChatError(_('Слишком много ролей.'), 409)
        role = SpaceRole(space=space, order=space.roles.count())
    role.name, role.color, role.perms, role.hoist = name, color, wanted, bool(hoist)
    role.save()
    for member in role.holders.all():
        _sync_member(space, member)
    _log(space, user, 'role', name)
    return role


def delete_role(space, user, role_id) -> None:
    _need(space, user, 'manage_roles')
    role = space.roles.filter(pk=role_id).first()
    if role is None:
        return
    holders = list(role.holders.all())
    threads = list(role.private_threads.all())
    _log(space, user, 'role', f'− {role.name}')
    role.delete()
    for member in holders:
        _sync_member(space, member)
    for thread in threads:
        _sync_thread(thread)


def set_member_roles(space, by, user, role_ids) -> None:
    """Какие свои роли есть у участника."""
    actor = _need(space, by, 'manage_roles')
    m = membership(space, user)
    if m is None:
        raise ChatError(_('Этого участника изменить нельзя.'), 403)
    roles = _role_ids(space, role_ids)
    extra = set()
    for r in roles:
        extra.update(r.perms)
    if not extra <= perms_of(actor):
        raise ChatError(_('Нельзя дать роль с правами, которых нет у вас.'), 403)
    m.roles.set(roles)
    _sync_member(space, m)
    _log(space, by, 'roles', f'{user.get_display_name()}: {", ".join(r.name for r in roles) or "—"}')


# ---------- люди ----------

def _invite_ok(inv) -> bool:
    return (inv.expires_at is None or inv.expires_at > timezone.now()) and (not inv.max_uses or inv.uses < inv.max_uses)


def by_code(code: str):
    if not code:
        return None
    space = Space.objects.filter(invite_code=code, closed=False).first()
    if space is not None:
        return space
    inv = SpaceInvite.objects.filter(code=code, space__closed=False).select_related('space').first()
    return inv.space if inv is not None and _invite_ok(inv) else None


def create_invite(space, user, hours: int = 0, max_uses: int = 0) -> SpaceInvite:
    """Приглашение со сроком (часы; 0 — бессрочно) и числом использований (0 — без ограничения)."""
    _need(space, user, 'manage_space')
    try:
        hours, max_uses = max(0, min(int(hours or 0), 24 * 30)), max(0, min(int(max_uses or 0), 10000))
    except (TypeError, ValueError):
        hours, max_uses = 0, 0
    inv = SpaceInvite.objects.create(space=space, code=secrets.token_urlsafe(9), creator=user, max_uses=max_uses,
                                     expires_at=timezone.now() + timedelta(hours=hours) if hours else None)
    _log(space, user, 'invite', str(_('новое приглашение')))
    return inv


def delete_invite(space, user, invite_id) -> None:
    _need(space, user, 'manage_space')
    space.invites.filter(pk=invite_id).delete()


def join(space, user, code: str = '') -> SpaceMember:
    if space.closed or not enabled():
        raise ChatError(_('Сообщество закрыто.'), 403)
    old = SpaceMember.objects.filter(space=space, user=user).first()
    if old is not None:
        if old.role == SpaceMember.BANNED:
            raise ChatError(_('Вас удалили из этого сообщества.'), 403)
        return old
    inv = None
    if code and code != space.invite_code:
        inv = SpaceInvite.objects.filter(space=space, code=code).first()
        if inv is None or not _invite_ok(inv):
            raise ChatError(_('Это приглашение больше не действует.'), 403)
    elif not space.is_public and code != space.invite_code:
        raise ChatError(_('Сюда можно попасть только по ссылке-приглашению.'), 403)
    with transaction.atomic():
        m = SpaceMember.objects.create(space=space, user=user)
        if inv is not None:
            # счётчик приглашения — одной операцией в базе: двое с последним «местом» не войдут оба
            took = (SpaceInvite.objects.filter(pk=inv.pk).filter(Q(max_uses=0) | Q(uses__lt=F('max_uses')))
                    .update(uses=F('uses') + 1))
            if not took:
                raise ChatError(_('Это приглашение больше не действует.'), 403)
        _sync_member(space, m)
        _recount(space)
    return m


def _expel(space, user) -> None:
    from .rooms import _forget
    for thread in space.threads.all():
        _revoke(thread, user.pk)
        _forget(thread, user)
    cache.delete(f'chat:nick:{space.pk}:{user.pk}')


def leave(space, user) -> None:
    m = membership(space, user)
    if m is None:
        return
    if m.role == SpaceMember.OWNER:
        heir = (space.members.filter(role=SpaceMember.ADMIN).exclude(user=user).order_by('joined_at').first()
                or space.members.filter(role__in=[SpaceMember.MOD, SpaceMember.MEMBER]).exclude(user=user).order_by('joined_at').first())
        if heir is None:
            return delete(space, user)
        set_role(space, None, heir.user, SpaceMember.OWNER)
    with transaction.atomic():
        _expel(space, user)
        m.delete()
        _recount(space)


def _outranks(actor, target) -> bool:
    return RANK.get(actor.role, 0) > RANK.get(target.role, 0) or actor.role == target.role == SpaceMember.MEMBER


def kick(space, by, user) -> None:
    """Удалить из сообщества: вернуться по ссылке нельзя (пока не разбанят)."""
    actor, target = _need(space, by, 'kick'), membership(space, user)
    if target is None or target.role == SpaceMember.OWNER or target.user_id == by.pk or not _outranks(actor, target):
        raise ChatError(_('Этого участника удалить нельзя.'), 403)
    with transaction.atomic():
        _expel(space, user)
        target.roles.clear()
        target.role = SpaceMember.BANNED
        target.save(update_fields=['role'])
        _recount(space)
    _log(space, by, 'kick', user.get_display_name())


def unban(space, by, user) -> None:
    _need(space, by, 'kick')
    SpaceMember.objects.filter(space=space, user=user, role=SpaceMember.BANNED).delete()
    _log(space, by, 'unban', user.get_display_name())


def banned(space) -> list:
    return list(space.members.filter(role=SpaceMember.BANNED).select_related('user'))


def timeout(space, by, user, key: str) -> None:
    """Тайм-аут: участник не может писать 5 минут / час / сутки / неделю. key='' — снять."""
    actor, target = _need(space, by, 'timeout'), membership(space, user)
    if target is None or target.role == SpaceMember.OWNER or target.user_id == by.pk or not _outranks(actor, target):
        raise ChatError(_('Этому участнику нельзя дать тайм-аут.'), 403)
    seconds = TIMEOUTS.get(key)
    target.muted_until = timezone.now() + timedelta(seconds=seconds) if seconds else None
    target.save(update_fields=['muted_until'])
    _log(space, by, 'timeout', f'{user.get_display_name()}: {key or "снят"}')


def check_write(thread, user) -> None:
    """Можно ли писать в канал сообщества (тайм-аут). Зовёт services._check_can_write."""
    until = SpaceMember.objects.filter(space_id=thread.space_id, user=user).values_list('muted_until', flat=True).first()
    if until and until > timezone.now():
        raise ChatError(_('У вас тайм-аут в этом сообществе до {t}.').format(t=timezone.localtime(until).strftime('%d.%m %H:%M')), 403)


def set_role(space, by, user, role: str) -> None:
    """Основная роль участника. by=None — служебный вызов (передача владения)."""
    actor = None
    if by is not None:
        actor = membership(space, by)
        if actor is None or actor.role not in (SpaceMember.OWNER, SpaceMember.ADMIN):
            raise ChatError(_('На это у вас нет прав в сообществе.'), 403)
        if role == SpaceMember.OWNER or (role == SpaceMember.ADMIN and actor.role != SpaceMember.OWNER):
            raise ChatError(_('Назначать админов может только владелец.'), 403)
    if role not in RANK:
        raise ChatError(_('Неизвестная роль'))
    m = membership(space, user)
    if m is None or (actor is not None and (m.role == SpaceMember.OWNER or (m.role == SpaceMember.ADMIN and actor.role != SpaceMember.OWNER))):
        raise ChatError(_('Этого участника изменить нельзя.'), 403)
    m.role = role
    m.save(update_fields=['role'])
    if role == SpaceMember.OWNER:
        Space.objects.filter(pk=space.pk).update(owner=user)
        Thread.objects.filter(space=space).update(owner=user)
    _sync_member(space, m)
    if by is not None:
        _log(space, by, 'rank', f'{user.get_display_name()}: {m.get_role_display()}')


def set_nick(space, user, nick: str) -> None:
    """Свой ник в этом сообществе (пусто — обычное имя). Не уникальный: рядом всегда виден профиль."""
    m = _need(space, user)
    m.nick = ' '.join((nick or '').split())[:32]
    m.save(update_fields=['nick'])
    cache.delete(f'chat:nick:{space.pk}:{user.pk}')


def nick_of(space_id, user) -> str:
    """Имя человека в сообществе: свой ник или обычное имя. Из кеша — зовётся на каждое сообщение."""
    key = f'chat:nick:{space_id}:{user.pk}'
    nick = cache.get(key)
    if nick is None:
        nick = SpaceMember.objects.filter(space_id=space_id, user=user).values_list('nick', flat=True).first() or ''
        cache.set(key, nick, 3600)
    if nick:
        return nick
    from apps.accounts import people as accounts_people  # общий «профиль для сообществ» (маска), если человек его завёл
    common = accounts_people.persona_of(user, accounts_people.SPACES)
    return common['name'] if common else user.get_display_name()


def avatar_of(user) -> str:
    """Аватар человека в сообществах: из общего «профиля для сообществ» (маска), иначе — основной."""
    from apps.accounts import people as accounts_people
    common = accounts_people.persona_of(user, accounts_people.SPACES)
    if common and common['avatar']:
        return common['avatar']
    return user.avatar.url if user.avatar else ''


def people(space, limit: int = 300) -> list:
    rows = list(space.members.exclude(role=SpaceMember.BANNED).select_related('user').prefetch_related('roles')[:limit])
    rows.sort(key=lambda m: (-RANK.get(m.role, 0), m.joined_at))
    return rows


def roster(space, viewer, limit: int = 200) -> list:
    """Список участников для боковой панели — как в Discord: группы по роли, внутри — сначала те, кто в сети.
    [{'title', 'color', 'people': [{'id','name','avatar','online','color'}]}]"""
    from apps.accounts import people as ppl
    groups, index = [], {}

    def bucket(key, title, color=''):
        if key not in index:
            index[key] = {'title': title, 'color': color, 'people': []}
            groups.append(index[key])
        return index[key]
    base = {SpaceMember.OWNER: str(_('Владелец')), SpaceMember.ADMIN: str(_('Админы')), SpaceMember.MOD: str(_('Модераторы'))}
    for m in people(space, limit):
        own = list(m.roles.all())
        top = next((r for r in own if r.hoist), None)
        if m.role in base:
            g = bucket(m.role, base[m.role])
        elif top is not None:
            g = bucket(f'r{top.pk}', top.name, top.color)
        else:
            g = bucket('members', str(_('Участники')))
        u = m.user
        name = m.nick or u.get_display_name()
        g['people'].append({'id': u.pk, 'name': name, 'avatar': avatar_of(u), 'online': ppl.quick_online(u, viewer),
                            'color': own[0].color if own else '', 'letter': (name or '?')[:1].upper(), 'hue': u.pk % 7})
    for g in groups:
        g['people'].sort(key=lambda p: (not p['online'], p['name'].casefold()))
    return groups


def mention_targets(thread, sender, body: str) -> set:
    """Кого упомянули в канале сообщества: @everyone (если есть право) и @название_роли."""
    text = (body or '').lower()
    if '@' not in text:
        return set()
    ids = set()
    if '@everyone' in text and can(thread.space, sender, 'mention_everyone'):
        ids.update(thread.participants.values_list('pk', flat=True))
    for role in thread.space.roles.all():
        if f'@{role.name.lower()}' in text:
            ids.update(role.holders.values_list('user_id', flat=True))
    ids.discard(sender.pk)
    return ids & set(thread.participants.values_list('pk', flat=True))


# ---------- доска задач (канбан) ----------

def tasks(space, user) -> dict:
    _need(space, user)
    out = {k: [] for k, _n in SpaceTask.STATUSES}
    for t in space.tasks.select_related('assignee', 'creator'):
        out[t.status].append(t)
    return out


def _task_editable(space, user, task) -> bool:
    return task.creator_id == user.pk or task.assignee_id == user.pk or can(space, user, 'manage_tasks')


def save_task(space, user, task_id=None, title: str = '', note: str = '', assignee_id=None, due=None) -> SpaceTask:
    _need(space, user)
    title = ' '.join((title or '').split())[:160]
    if len(title) < 2:
        raise ChatError(_('Напишите, что нужно сделать.'))
    task = space.tasks.filter(pk=task_id).first() if task_id else None
    if task is None:
        if space.tasks.count() >= MAX_TASKS:
            raise ChatError(_('На доске слишком много задач — удалите готовые.'), 409)
        task = SpaceTask(space=space, creator=user, order=space.tasks.count())
    elif not _task_editable(space, user, task):
        raise ChatError(_('Эту задачу может менять автор, исполнитель или админ.'), 403)
    task.title, task.note = title, (note or '').strip()[:1000]
    if assignee_id is not None:
        who = space.members.exclude(role=SpaceMember.BANNED).filter(user_id=assignee_id).first() if str(assignee_id).isdigit() else None
        task.assignee = who.user if who is not None else None
    if due is not None:
        try:
            task.due = date.fromisoformat(str(due)[:10]) if due else None
        except ValueError:
            task.due = None
    task.save()
    return task


def move_task(space, user, task_id, status: str) -> None:
    """Взять задачу в работу / завершить / вернуть может любой участник — так и работают вместе."""
    _need(space, user)
    if status not in dict(SpaceTask.STATUSES):
        raise ChatError(_('Неизвестная колонка'))
    task = space.tasks.filter(pk=task_id).first()
    if task is None:
        return
    task.status = status
    if status == SpaceTask.DOING and task.assignee_id is None:
        task.assignee = user                                # взял в работу — стал исполнителем
    task.save()


def delete_task(space, user, task_id) -> None:
    _need(space, user)
    task = space.tasks.filter(pk=task_id).first()
    if task is not None:
        if not _task_editable(space, user, task):
            raise ChatError(_('Эту задачу может менять автор, исполнитель или админ.'), 403)
        task.delete()


# ---------- что показать ----------

def mine(user) -> list:
    if not getattr(user, 'is_authenticated', False):
        return []
    ids = SpaceMember.objects.filter(user=user).exclude(role=SpaceMember.BANNED).values('space_id')
    return list(Space.objects.filter(pk__in=ids, closed=False).order_by('title'))


def catalog(q: str = ''):
    qs = Space.objects.filter(is_public=True, closed=False)
    q = (q or '').strip()[:60]
    if q:
        from apps.core.textsearch import icontains
        qs = qs.filter(icontains('title', q) | icontains('about', q))
    return qs.order_by('-platform_verified', '-members_count', '-created_at')


def tree(space, user) -> dict:
    """Сообщество для экрана: категории с каналами (только те, что человеку видны), непрочитанное, моя роль и права.
    {'space', 'me', 'perms', 'groups': [{'id','title','channels':[{'id','title','kind','unread','private'…}]}]}"""
    from . import services, voice
    me = membership(space, user)
    unread, visible = {}, None
    if me is not None:
        unread = {t.pk: t.unread for t, _o, _m in services.inbox(user, space=space)}
        visible = set(Thread.objects.filter(space=space, participants=user).values_list('pk', flat=True))
    cats = list(space.categories.all())
    groups = [{'id': c.pk, 'title': c.title, 'channels': []} for c in cats] + [{'id': 0, 'title': '', 'channels': []}]
    index = {g['id']: g for g in groups}
    for t in space.threads.order_by('space_order', 'pk'):
        if t.space_private and (visible is None or t.pk not in visible):
            continue                                        # закрытый канал видят только те, кому он открыт
        index.get(t.space_category_id or 0, index[0])['channels'].append(
            {'id': t.pk, 'title': t.title, 'kind': NEWS if t.kind == Thread.CHANNEL else TEXT, 'unread': unread.get(t.pk, 0),
             'order': t.space_order, 'private': t.space_private, 'topic': t.space_topic})
    for v in space.voices.all():
        index.get(v.category_id or 0, index[0])['channels'].append(
            {'id': v.pk, 'title': v.title, 'kind': VOICE, 'unread': 0, 'order': v.order, 'private': False, 'topic': '',
             'people': voice.present(v.pk)})
    for g in groups:
        g['channels'].sort(key=lambda x: (x['kind'] == VOICE, x['order']))
    return {'space': space, 'me': me, 'perms': perms_of(me), 'groups': [g for g in groups if g['channels'] or g['id']],
            'unread': sum(unread.values()), 'first': next((ch['id'] for g in groups for ch in g['channels'] if ch['kind'] != VOICE), None)}


__all__ = ['add_category', 'add_channel', 'banned', 'by_code', 'can', 'can_view', 'catalog', 'check_write', 'create', 'create_invite',
           'delete', 'delete_category', 'delete_channel', 'delete_invite', 'delete_role', 'delete_task', 'enabled', 'join', 'kick',
           'leave', 'membership', 'mention_targets', 'mine', 'move_task', 'nick_of', 'people', 'perms_of', 'rename_channel',
           'reset_invite', 'roster', 'save_role', 'save_task', 'set_channel', 'set_member_roles', 'set_nick', 'set_role', 'tasks',
           'timeout', 'tree', 'unban', 'update']
