"""Люди — «как в Telegram»: имя пользователя (@имя), «в сети / был(а) в 14:05», кто видит
номер и соцсети, близкие друзья, поиск по имени пользователя и по номеру.

Правила приватности — в одном месте: сайт и приложение спрашивают здесь, что показать
конкретному зрителю. Номер и ссылки никогда не отдаются «на всякий случай» — только если
владелец разрешил именно этому человеку.
"""
import re
from datetime import timedelta
from urllib.parse import urlsplit

from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import CloseFriend, SocialLink, User, UserBlock
from .phones import digits, phone_key

HANDLE = re.compile(r'^[a-z][a-z0-9_]{3,31}$')
# имена, которыми мог бы прикинуться мошенник («поддержка», «админ»): обычному человеку недоступны,
# сотрудникам ilm4 — можно (официальный канал @ilm4 создаёт владелец площадки)
RESERVED = {'admin', 'ilm4', 'support', 'help', 'official', 'moderator', 'system', 'null', 'api', 'chat', 'channel',
            'channels', 'group', 'groups', 'join', 'news', 'ilm4_support', 'ilm4_admin', 'administrator'}
ONLINE = timedelta(minutes=2)          # «в сети»: приложение и сайт отмечаются раз в минуту
TOUCH_EVERY = 45                       # не чаще раза в 45 секунд пишем в базу
MAX_LINKS = 12
NEW_CHATS_PER_DAY = 30                 # новых диалогов с незнакомыми в сутки — против рассылок


class PeopleError(Exception):
    def __init__(self, message, status=400):
        super().__init__(str(message))
        self.message, self.status = str(message), status


# ---------- имя пользователя ----------

def clean_handle(value, user=None, room=None) -> str | None:
    """Проверить @имя. Одно пространство имён у людей, групп и каналов — как в Telegram."""
    from apps.chat.models import Thread

    value = (value or '').strip().lstrip('@').lower()
    if not value:
        return None
    if not HANDLE.match(value):
        raise PeopleError(_('Имя: латинские буквы, цифры и «_», от 4 до 32 знаков, первая — буква. Например: ali_2024'))
    if value in RESERVED and not (user is not None and user.is_staff):
        raise PeopleError(_('Это имя зарезервировано за командой ilm4 — выберите другое.'))
    people = User.objects.filter(handle=value)
    rooms = Thread.objects.filter(handle=value)
    if user is not None and room is None:
        people = people.exclude(pk=user.pk)
    if room:
        rooms = rooms.exclude(pk=room.pk)
    if people.exists() or rooms.exists():
        raise PeopleError(_('Это имя уже занято.'))
    return value


# ---------- «в сети» ----------

def touch(user) -> None:
    """Отметить, что человек сейчас в сети. Зовётся на каждом запросе, в базу пишет раз в 45 секунд."""
    if not getattr(user, 'pk', None) or not user.is_authenticated:
        return
    if cache.add(f'seen:{user.pk}', 1, TOUCH_EVERY):
        now = timezone.now()
        User.objects.filter(pk=user.pk).update(last_seen_at=now)
        user.last_seen_at = now


def is_close(owner, viewer) -> bool:
    """viewer в «близких друзьях» у owner."""
    if viewer is None or not getattr(viewer, 'pk', None) or owner.pk == viewer.pk:
        return False
    return CloseFriend.objects.filter(owner=owner, friend=viewer).exists()


def _allowed(level: str, close: bool) -> bool:
    return level == User.ALL or (level == User.CLOSE and close)


def presence(person, viewer, close=None) -> dict:
    """Что зритель знает о времени человека в сети.

    {'online': bool, 'seen': ISO или None, 'hidden': bool}. hidden — «был(а) недавно»: человек скрыл
    время, либо зритель сам его скрывает (взаимность, как в Telegram: скрыл своё — не видишь чужое).
    """
    if viewer is not None and getattr(viewer, 'pk', None) == person.pk:
        return {'online': True, 'seen': None, 'hidden': False}
    if viewer is None or not getattr(viewer, 'pk', None):
        return {'online': False, 'seen': None, 'hidden': True}
    if close is None:
        close = person.seen_privacy == User.CLOSE and is_close(person, viewer)
    shows = _allowed(person.seen_privacy, close)
    mutual = viewer.seen_privacy == User.ALL or (viewer.seen_privacy == User.CLOSE and is_close(viewer, person))
    if not (shows and mutual):
        return {'online': False, 'seen': None, 'hidden': True}
    seen = person.last_seen_at
    return {'online': bool(seen and timezone.now() - seen < ONLINE), 'seen': seen.isoformat() if seen else None,
            'hidden': False}


def status_text(pr: dict) -> str:
    """Подпись под именем, как в Telegram: «в сети», «был(а) в 14:05», «был(а) недавно»."""
    from datetime import datetime

    from django.utils.formats import date_format
    if pr['online']:
        return _('в сети')
    if pr['hidden']:
        return _('был(а) недавно')
    if not pr['seen']:
        return _('был(а) давно')
    local = timezone.localtime(datetime.fromisoformat(pr['seen']))
    today = timezone.localdate()
    hm = local.strftime('%H:%M')
    if local.date() == today:
        return _('был(а) в {t}').format(t=hm)
    if local.date() == today - timedelta(days=1):
        return _('был(а) вчера в {t}').format(t=hm)
    if (today - local.date()).days < 300:
        return _('был(а) {d} в {t}').format(d=date_format(local, 'j E'), t=hm)
    return _('был(а) {d}').format(d=date_format(local, 'j E Y'))


def quick_online(person, viewer) -> bool:
    """Зелёная точка в списках — без лишних запросов: только у тех, кто показывает время всем."""
    seen = person.last_seen_at
    return bool(seen and person.seen_privacy == User.ALL and viewer.seen_privacy != User.NOBODY
                and timezone.now() - seen < ONLINE)


def phone_for(person, viewer, close=None) -> str:
    """Номер, если владелец разрешил его видеть этому человеку (и номер подтверждён либо это он сам)."""
    if not person.phone:
        return ''
    if viewer is not None and getattr(viewer, 'pk', None) == person.pk:
        return person.phone
    if close is None:
        close = person.phone_privacy == User.CLOSE and is_close(person, viewer)
    return person.phone if _allowed(person.phone_privacy, close) else ''


# ---------- соцсети ----------

# сеть → (шаблон ссылки, допустимые домены для вставленной ссылки)
SOCIAL = {
    'telegram': ('https://t.me/{}', ('t.me', 'telegram.me')),
    'instagram': ('https://instagram.com/{}', ('instagram.com',)),
    'youtube': ('https://youtube.com/@{}', ('youtube.com', 'youtu.be')),
    'tiktok': ('https://tiktok.com/@{}', ('tiktok.com',)),
    'whatsapp': ('https://wa.me/{}', ('wa.me', 'whatsapp.com')),
    'facebook': ('https://facebook.com/{}', ('facebook.com', 'fb.com')),
    'x': ('https://x.com/{}', ('x.com', 'twitter.com')),
    'vk': ('https://vk.com/{}', ('vk.com',)),
    'github': ('https://github.com/{}', ('github.com',)),
    'linkedin': ('https://linkedin.com/in/{}', ('linkedin.com',)),
}
_NICK = re.compile(r'^[\w.\-]{2,60}$')
_KINDS = dict(SocialLink.KINDS)


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or '').lower().removeprefix('www.').removeprefix('m.')
    except ValueError:
        return ''


def clean_link(kind: str, value: str) -> str:
    """Привести к виду, который хранится: ник без «@» либо полная https-ссылка. Мусор — отказ."""
    value = (value or '').strip()[:120]
    if kind not in _KINDS or not value:
        raise PeopleError(_('Укажите сеть и имя в ней.'))
    is_url = value.lower().startswith(('http://', 'https://'))
    if kind in SOCIAL:
        if is_url:
            if _host(value) not in SOCIAL[kind][1]:
                raise PeopleError(_('Ссылка не похожа на {name}.').format(name=_KINDS[kind]))
            return 'https://' + value.split('://', 1)[1]
        value = value.lstrip('@').strip('/')
        if kind == 'whatsapp':
            value = digits(value)
            if not 9 <= len(value) <= 15:
                raise PeopleError(_('WhatsApp: укажите номер с кодом страны.'))
            return value
        if not _NICK.match(value):
            raise PeopleError(_('{name}: укажите имя (ник) или ссылку на профиль.').format(name=_KINDS[kind]))
        return value
    if kind == 'website':
        if not is_url:
            value = 'https://' + value
        if '.' not in _host(value):
            raise PeopleError(_('Сайт: укажите адрес, например example.com'))
        return 'https://' + value.split('://', 1)[1]
    if is_url and '.' not in _host(value):
        raise PeopleError(_('Ссылка указана неверно.'))
    return value


def link_url(kind: str, value: str) -> str:
    """Куда ведёт ссылка (только http/https). Пусто — показываем как текст (Discord, «Другое»)."""
    if value.lower().startswith(('http://', 'https://')):
        return value
    return SOCIAL[kind][0].format(value) if kind in SOCIAL else ''


def set_links(user, rows) -> None:
    """Заменить соцсети целиком: rows = [{'kind', 'value', 'privacy'}, …]."""
    levels = dict(User.PRIVACY)
    clean = []
    for row in list(rows or [])[:MAX_LINKS]:
        if not isinstance(row, dict) or not str(row.get('value', '')).strip():
            continue
        kind = str(row.get('kind', ''))
        privacy = str(row.get('privacy', User.ALL))
        clean.append(SocialLink(user=user, kind=kind, value=clean_link(kind, str(row['value'])),
                                privacy=privacy if privacy in levels else User.ALL, order=len(clean)))
    user.social_links.all().delete()
    SocialLink.objects.bulk_create(clean)


def links_for(person, viewer, close=None) -> list:
    me = viewer is not None and getattr(viewer, 'pk', None) == person.pk
    rows = list(person.social_links.all())
    if close is None:
        close = any(x.privacy == User.CLOSE for x in rows) and is_close(person, viewer)
    out = []
    for x in rows:
        if me or _allowed(x.privacy, close):
            item = {'kind': x.kind, 'title': str(_KINDS.get(x.kind, x.kind)), 'value': x.value,
                    'url': link_url(x.kind, x.value)}
            if me:
                item['privacy'] = x.privacy
            out.append(item)
    return out


# ---------- близкие друзья ----------

def set_close(owner, friend, on: bool) -> bool:
    if owner.pk == friend.pk:
        raise PeopleError(_('Себя добавить нельзя.'))
    if on:
        CloseFriend.objects.get_or_create(owner=owner, friend=friend)
    else:
        CloseFriend.objects.filter(owner=owner, friend=friend).delete()
    return on


def close_friends(owner):
    return User.objects.filter(close_of__owner=owner, is_active=True).order_by('close_of__created_at')


# ---------- поиск и контакты ----------

def _hit(key: str, max_hits: int, window: int) -> None:
    cache.add(key, 0, window)
    try:
        hits = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)
        hits = 1
    if hits > max_hits:
        raise PeopleError(_('Слишком часто — подождите немного.'), 429)


def contacts(viewer, limit: int = 200):
    """С кем у человека уже есть личные диалоги — его «контакты»."""
    from apps.chat.models import Thread
    mine = Thread.objects.filter(kind=Thread.DIRECT, participants=viewer)
    blocked = UserBlock.ids_for(viewer)
    return list(User.objects.filter(chat_threads__in=mine, is_active=True).exclude(pk=viewer.pk)
                .exclude(pk__in=blocked).distinct().order_by('-last_seen_at')[:limit])


def search(viewer, q: str, limit: int = 20) -> list:
    """Найти человека: по @имени (начало имени) или по номеру телефона (целиком).

    По номеру находятся только те, кто это разрешил и подтвердил номер; сам номер в ответе не показывается.
    Перебор номеров ограничен: 30 поисков по номеру в час.
    """
    q = (q or '').strip()[:60]
    blocked = UserBlock.ids_for(viewer)
    base = User.objects.filter(is_active=True).exclude(pk=viewer.pk).exclude(pk__in=blocked)
    number = digits(q)
    if len(number) >= 9 and re.fullmatch(r'[\d\s()+\-]+', q):
        _hit(f'people_phone:{viewer.pk}', 30, 3600)
        return list(base.filter(phone_key=phone_key(number), findable_by_phone=True,
                                phone_verified_at__isnull=False)[:limit])
    name = q.lstrip('@').lower()
    if not re.fullmatch(r'[a-z0-9_]{3,32}', name):
        return []
    found = list(base.filter(handle__startswith=name).order_by('handle')[:limit])
    found.sort(key=lambda u: u.handle != name)          # точное совпадение — первым
    return found


def check_new_chat(viewer, other) -> None:
    """Перед первым диалогом с незнакомым: не больше 30 новых диалогов в сутки (сотрудникам — без ограничений)."""
    if not viewer.is_staff:
        _hit(f'new_chats:{viewer.pk}', NEW_CHATS_PER_DAY, 86400)
