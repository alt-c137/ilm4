"""Группы и каналы (docs/MESSENGER.md §6).

Группа — общий чат: пишут все участники. Канал — лента: пишут владелец и админы,
остальные читают (канал мечети, учителя, организации). Обе — тот же Thread, что и личный
диалог: шифрование, вложения, файлы, отложенные сообщения работают так же.

Отличия от личного диалога:
* участник — запись Member (роль, «без звука», до какого момента прочитано);
* вступают по ссылке-приглашению, а в публичные — из каталога или по адресу /c/<имя>/;
* прочитанность считается по Member.last_read_at (в личном чате — по Message.read_at);
* колокольчик на каждое сообщение не дёргаем: тем, у кого не «без звука», уходит пуш.

Остальной код вызывает только функции отсюда и из services.py.
"""
import secrets

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Member, Thread
from .services import ChatError

CREATE_PER_DAY = 5                 # групп и каналов в сутки на человека — против спама
ADD_AT_ONCE = 50


def settings():
    from apps.core.models import SiteSettings
    return SiteSettings.get_solo()


def enabled(kind: str) -> bool:
    st = settings()
    return st.chat_groups_enabled if kind == Thread.GROUP else st.chat_channels_enabled if kind == Thread.CHANNEL else True


def can_create(user, kind: str) -> bool:
    if not enabled(kind):
        return False
    return not (kind == Thread.CHANNEL and settings().chat_channels_staff_only and not user.is_staff)


def visible_kinds() -> list:
    """Какие виды чатов показывать (выключенные в админке скрываются вместе с содержимым)."""
    return [Thread.DIRECT] + [k for k in (Thread.GROUP, Thread.CHANNEL) if enabled(k)]


# ---------- кто есть кто ----------

def membership(thread, user):
    if not getattr(user, 'is_authenticated', False):
        return None
    return Member.objects.filter(thread=thread, user=user).exclude(role=Member.BANNED).first()


def role_of(thread, user) -> str:
    m = membership(thread, user)
    return m.role if m else ''


def is_admin(thread, user) -> bool:
    return role_of(thread, user) in (Member.OWNER, Member.ADMIN)


def can_read(thread, user) -> bool:
    """Читать могут участники; публичную группу или канал — любой вошедший (как предпросмотр в Telegram)."""
    if not getattr(user, 'is_authenticated', False):
        return False
    if not thread.is_room:
        return thread.participants.filter(pk=user.pk).exists()
    if not enabled(thread.kind):
        return False
    if thread.participants.filter(pk=user.pk).exists():
        return True
    return thread.is_public and not thread.closed and not Member.objects.filter(
        thread=thread, user=user, role=Member.BANNED).exists()


def can_post(thread, user) -> bool:
    m = membership(thread, user)
    if m is None or thread.closed or not enabled(thread.kind):
        return False
    if thread.is_channel or thread.only_admins_post:
        return m.is_admin
    return True


def check_post(thread, user) -> None:
    if thread.closed:
        raise ChatError(_('Чат закрыт модератором.'), 403)
    if not can_post(thread, user):
        raise ChatError(_('В канале пишут только его авторы.') if thread.is_channel
                        else _('Писать здесь могут только участники.'), 403)


# ---------- создание и настройки ----------

def clean_handle(value, thread=None, user=None) -> str | None:
    """Публичное имя группы / канала. Имена общие с людьми (@имя); «ilm4», «support» и подобные — только сотрудникам."""
    from apps.accounts import people
    try:
        return people.clean_handle(value, user=user, room=thread if thread is not None else False)
    except people.PeopleError as exc:
        raise ChatError(exc.message) from exc


def _avatar(upload):
    if not upload:
        return None
    from django.core.exceptions import ValidationError

    from apps.core.uploads import clean_image
    try:
        return clean_image(upload)
    except ValidationError as exc:
        raise ChatError(' '.join(exc.messages)) from exc


def create(user, kind: str, title: str, about: str = '', is_public: bool = False, handle: str = '', avatar=None) -> Thread:
    from django.core.cache import cache

    from apps.accounts import phone_verify
    if kind not in (Thread.GROUP, Thread.CHANNEL):
        raise ChatError(_('Неизвестный вид чата'))
    if not can_create(user, kind):
        raise ChatError(_('Эта функция сейчас отключена'), 403)
    if phone_verify.needed(user, 'publish'):          # один номер — один аккаунт: спам-каналы пачками не создать
        raise ChatError(_('Создавать группы и каналы можно только с подтверждённым номером.'), 403)
    title = (title or '').strip()[:120]
    if len(title) < 2:
        raise ChatError(_('Дайте название — хотя бы два знака.'))
    key = f'rooms:new:{user.pk}'
    if cache.get(key, 0) >= CREATE_PER_DAY and not user.is_staff:
        raise ChatError(_('Сегодня вы уже создали много групп и каналов. Попробуйте завтра.'), 429)
    handle = clean_handle(handle, user=user) if is_public else None
    if is_public and not handle and kind == Thread.CHANNEL:
        raise ChatError(_('Публичному каналу нужно имя — по нему его находят.'))
    with transaction.atomic():
        thread = Thread.objects.create(kind=kind, title=title, about=(about or '').strip()[:500], owner=user,
                                       is_public=bool(is_public), handle=handle, invite_code=secrets.token_urlsafe(12),
                                       avatar=_avatar(avatar), members_count=1)
        thread.participants.add(user)
        Member.objects.create(thread=thread, user=user, role=Member.OWNER, last_read_at=timezone.now())
    cache.set(key, cache.get(key, 0) + 1, 86400)
    return thread


def update(thread, user, data, avatar=None) -> Thread:
    if not is_admin(thread, user):
        raise ChatError(_('Менять настройки могут владелец и админы.'), 403)
    fields = []
    if 'title' in data:
        title = str(data['title']).strip()[:120]
        if len(title) < 2:
            raise ChatError(_('Дайте название — хотя бы два знака.'))
        thread.title = title
        fields.append('title')
    if 'about' in data:
        thread.about = str(data['about']).strip()[:500]
        fields.append('about')
    if 'only_admins_post' in data and thread.kind == Thread.GROUP:
        thread.only_admins_post = str(data['only_admins_post']).lower() in ('1', 'true', 'on')
        fields.append('only_admins_post')
    if 'is_public' in data or 'handle' in data:
        public = str(data.get('is_public', thread.is_public)).lower() in ('1', 'true', 'on')
        handle = clean_handle(data.get('handle', thread.handle or ''), thread, user=user) if public else None
        if public and not handle and thread.is_channel:
            raise ChatError(_('Публичному каналу нужно имя — по нему его находят.'))
        thread.is_public, thread.handle = public, handle
        fields += ['is_public', 'handle']
    if avatar:
        thread.avatar = _avatar(avatar)
        fields.append('avatar')
    if fields:
        thread.save(update_fields=[*fields, 'updated_at'])
    return thread


def reset_invite(thread, user) -> str:
    """Новая ссылка-приглашение: старая перестаёт работать."""
    if not is_admin(thread, user):
        raise ChatError(_('Нет доступа'), 403)
    thread.invite_code = secrets.token_urlsafe(12)
    thread.save(update_fields=['invite_code'])
    return thread.invite_code


def delete(thread, user) -> None:
    if role_of(thread, user) != Member.OWNER and not user.is_staff:
        raise ChatError(_('Удалить может только владелец.'), 403)
    for m in thread.messages.exclude(attachment='').exclude(attachment__isnull=True):
        m.attachment.delete(save=False)
    thread.delete()


# ---------- вступить, выйти, участники ----------

def _recount(thread) -> None:
    Thread.objects.filter(pk=thread.pk).update(members_count=thread.participants.count())


def by_code(code: str):
    return Thread.objects.filter(invite_code=code, closed=False).exclude(kind=Thread.DIRECT).first() if code else None


def by_handle(handle: str):
    return Thread.objects.filter(handle=(handle or '').lower(), closed=False).exclude(kind=Thread.DIRECT).first()


def join(thread, user, code: str = '') -> Member:
    """Вступить: в публичный — свободно, в закрытый — по коду приглашения."""
    if not thread.is_room or not enabled(thread.kind):
        raise ChatError(_('Не найдено'), 404)
    if thread.closed:
        raise ChatError(_('Чат закрыт модератором.'), 403)
    if not thread.is_public and (not code or code != thread.invite_code):
        raise ChatError(_('Сюда можно попасть только по ссылке-приглашению.'), 403)
    return _add(thread, user)


def _add(thread, user, role=Member.MEMBER) -> Member:
    with transaction.atomic():
        thread = Thread.objects.select_for_update().get(pk=thread.pk)
        m = Member.objects.filter(thread=thread, user=user).first()
        if m and m.role == Member.BANNED:
            raise ChatError(_('Вас удалили из этого чата.'), 403)
        if m:
            return m
        if thread.kind == Thread.GROUP and thread.members_count >= settings().chat_group_max_members:
            raise ChatError(_('В группе уже максимум участников.'), 409)
        m = Member.objects.create(thread=thread, user=user, role=role, last_read_at=timezone.now())
        thread.participants.add(user)
        _recount(thread)
    return m


def add_members(thread, by, users) -> int:
    """Админ добавляет людей — только тех, с кем у него уже есть личный диалог (иначе это рассылка спама)."""
    if not is_admin(thread, by):
        raise ChatError(_('Добавлять участников могут владелец и админы.'), 403)
    from django.contrib.auth import get_user_model
    known = set(get_user_model().objects.filter(chat_threads__in=Thread.objects.filter(kind=Thread.DIRECT, participants=by))
                .values_list('pk', flat=True))
    added = 0
    for u in list(users)[:ADD_AT_ONCE]:
        if u.pk == by.pk or u.pk not in known or not u.is_active:
            continue
        try:
            before = Member.objects.filter(thread=thread, user=u).exists()
            _add(thread, u)
            added += 0 if before else 1
        except ChatError:
            continue
    return added


def leave(thread, user) -> None:
    m = membership(thread, user)
    if m is None:
        return
    if m.role == Member.OWNER:
        heir = (thread.members.filter(role=Member.ADMIN).exclude(user=user).order_by('joined_at').first()
                or thread.members.filter(role=Member.MEMBER).exclude(user=user).order_by('joined_at').first())
        if heir is None:                      # последний человек ушёл — чат больше никому не нужен
            return delete(thread, user)
        heir.role = Member.OWNER
        heir.save(update_fields=['role'])
        Thread.objects.filter(pk=thread.pk).update(owner=heir.user)
    m.delete()
    thread.participants.remove(user)
    _recount(thread)


def remove_member(thread, by, user) -> None:
    """Удалить участника: вернуться по ссылке он уже не сможет."""
    mine, target = membership(thread, by), Member.objects.filter(thread=thread, user=user).first()
    if mine is None or not mine.is_admin or target is None:
        raise ChatError(_('Нет доступа'), 403)
    if target.role == Member.OWNER or (target.role == Member.ADMIN and mine.role != Member.OWNER):
        raise ChatError(_('Этого участника удалить нельзя.'), 403)
    target.role = Member.BANNED
    target.save(update_fields=['role'])
    thread.participants.remove(user)
    _recount(thread)


def set_admin(thread, by, user, admin: bool) -> None:
    if role_of(thread, by) != Member.OWNER:
        raise ChatError(_('Назначать админов может только владелец.'), 403)
    target = membership(thread, user)
    if target is None or target.role == Member.OWNER:
        raise ChatError(_('Нет такого участника.'), 404)
    target.role = Member.ADMIN if admin else Member.MEMBER
    target.save(update_fields=['role'])


def set_muted(thread, user, muted: bool) -> None:
    Member.objects.filter(thread=thread, user=user).update(muted=bool(muted))


def members(thread, limit: int = 200):
    """Сначала владелец и админы, потом остальные по времени вступления."""
    order = {Member.OWNER: 0, Member.ADMIN: 1, Member.MEMBER: 2}
    rows = list(thread.members.exclude(role=Member.BANNED).select_related('user').order_by('joined_at')[:limit * 2])
    rows.sort(key=lambda m: order.get(m.role, 3))
    return rows[:limit]


# ---------- прочитанность и уведомления ----------

def mark_read(thread, user) -> None:
    """Открыл группу / канал — всё до этого момента прочитано. В канале заодно считаем просмотры постов."""
    m = membership(thread, user)
    if m is None:
        return
    now = timezone.now()
    if thread.is_channel:
        fresh = thread.messages.delivered().exclude(sender=user)
        if m.last_read_at:
            fresh = fresh.filter(created_at__gt=m.last_read_at)
        fresh.update(views=F('views') + 1)
    Member.objects.filter(pk=m.pk).update(last_read_at=now)


def notify(thread, sender, text: str, silent: bool = False) -> None:
    """Пуш участникам, у кого не «без звука». Колокольчик не трогаем: непрочитанное видно в списке чатов."""
    import threading

    from django.conf import settings as dj
    if getattr(dj, 'PUSH_DISABLED', False):
        return
    title = thread.title
    body = text[:140] if thread.is_channel else f'{sender.get_display_name()}: {text[:120]}'
    url = f'/chat/{thread.pk}/'
    thread_id, sender_id = thread.pk, sender.pk

    def run():
        from django.db import connection

        from apps.api.models import PushDevice
        from apps.api.push import _send
        try:
            users = (Member.objects.filter(thread_id=thread_id, muted=False).exclude(role=Member.BANNED)
                     .exclude(user_id=sender_id).values('user_id'))
            tokens = list(PushDevice.objects.filter(user_id__in=users).values_list('token', flat=True))
            for i in range(0, len(tokens), 100):          # Expo принимает до 100 сообщений за запрос
                _send([{'to': t, 'title': title, 'body': body, 'data': {'url': url},
                        **({} if silent else {'sound': 'default'})} for t in tokens[i:i + 100]])
        finally:
            connection.close()
    transaction.on_commit(lambda: threading.Thread(target=run, daemon=True).start())


# ---------- каталог ----------

def catalog(q: str = '', kind: str = ''):
    """Публичные каналы и группы: сначала официальные, потом по числу участников."""
    qs = Thread.objects.filter(is_public=True, closed=False, kind__in=[k for k in visible_kinds() if k != Thread.DIRECT])
    if kind in (Thread.GROUP, Thread.CHANNEL):
        qs = qs.filter(kind=kind)
    q = (q or '').strip()[:60]
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(about__icontains=q) | Q(handle__icontains=q.lstrip('@').lower()))
    return qs.order_by('-platform_verified', '-members_count', '-updated_at')


def info(thread, user) -> dict:
    """Всё о группе / канале для клиента (сайт и приложение)."""
    m = membership(thread, user)
    return {
        'kind': thread.kind, 'title': thread.title, 'about': thread.about, 'handle': thread.handle or '',
        'public': thread.is_public, 'verified': thread.platform_verified, 'closed': thread.closed,
        'members': thread.members_count, 'role': m.role if m else '', 'member': m is not None,
        'admin': bool(m and m.is_admin), 'muted': bool(m and m.muted), 'can_post': can_post(thread, user),
        'only_admins_post': thread.only_admins_post,
        'invite': thread.invite_code if (m and (m.is_admin or thread.kind == Thread.GROUP)) or thread.is_public else '',
    }

