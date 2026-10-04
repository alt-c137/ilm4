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

# Имя пользователя (@имя) — правила Telegram: латинские буквы, цифры и «_»; первая — буква; «_» не в конце и не два подряд.
# Отличие одно: в Telegram минимум 5 знаков (короче — только с аукциона), у нас — от HANDLE_MIN.
HANDLE_MIN, HANDLE_MAX = 3, 32
HANDLE = re.compile(rf'^[a-z][a-z0-9_]{{{HANDLE_MIN - 1},{HANDLE_MAX - 1}}}$')
# имена, которыми мог бы прикинуться мошенник («поддержка», «админ»): обычному человеку недоступны,
# сотрудникам ilm4 — можно (официальный канал @ilm4 создаёт владелец площадки)
RESERVED = {'admin', 'ilm4', 'support', 'help', 'official', 'moderator', 'system', 'null', 'api', 'chat', 'channel',
            'channels', 'group', 'groups', 'join', 'news', 'ilm4_support', 'ilm4_admin', 'administrator'}
ONLINE = timedelta(minutes=2)          # «в сети»: приложение и сайт отмечаются раз в минуту
TOUCH_EVERY = 45                       # не чаще раза в 45 секунд пишем в базу
MAX_LINKS = 12
NEW_CHATS_PER_DAY = 30                 # новых диалогов с незнакомыми в сутки — против рассылок
NEW_CHATS_NO_PHONE = 5                 # …а без подтверждённого номера — меньше: аккаунт без номера заводится за минуту


class PeopleError(Exception):
    def __init__(self, message, status=400):
        super().__init__(str(message))
        self.message, self.status = str(message), status


# ---------- имя пользователя ----------

def handle_problem(value: str) -> str:
    """Что не так с написанием имени (пусто — всё в порядке). Сообщения — как подсказки под полем в Telegram."""
    if not re.fullmatch(r'[a-z0-9_]*', value):
        return str(_('Можно только латинские буквы, цифры и «_».'))
    if value[:1].isdigit() or value.startswith('_'):
        return str(_('Имя должно начинаться с буквы.'))
    if len(value) < HANDLE_MIN:
        return str(_('Имя слишком короткое — нужно хотя бы {n} знака.').format(n=HANDLE_MIN))
    if len(value) > HANDLE_MAX:
        return str(_('Имя слишком длинное — не больше {n} знаков.').format(n=HANDLE_MAX))
    if value.endswith('_') or '__' in value:
        return str(_('Знак «_» не может стоять в конце или два раза подряд.'))
    return ''


def clean_handle(value, user=None, room=None) -> str | None:
    """Проверить @имя. Одно пространство имён у людей, групп и каналов — как в Telegram."""
    from apps.chat.models import Thread

    value = (value or '').strip().lstrip('@').lower()
    if not value:
        return None
    problem = handle_problem(value)
    if problem or not HANDLE.match(value):
        raise PeopleError(problem or _('Можно только латинские буквы, цифры и «_».'))
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


def handle_state(value, user=None, room=None) -> dict:
    """Для проверки «на лету», пока человек печатает: {'ok', 'text'} — «Имя свободно» или что не так."""
    value = (value or '').strip().lstrip('@').lower()
    if not value:
        return {'ok': None, 'text': ''}
    if room is None and user is not None and value == (user.handle or ''):
        return {'ok': True, 'text': str(_('Это ваше имя.'))}
    try:
        clean_handle(value, user=user, room=room)
    except PeopleError as exc:
        return {'ok': False, 'text': exc.message}
    return {'ok': True, 'text': str(_('Имя @{name} свободно.').format(name=value))}


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


def can_invite(owner, by) -> bool:
    """Можно ли этому человеку добавить owner в группу (настройка «кто может добавлять меня в группы»)."""
    return _allowed(owner.invite_privacy, is_close(owner, by))


def can_see_counts(owner, viewer=None) -> bool:
    """Видны ли этому человеку счётчики профиля (записи, подписчики, подписки). Себе — всегда."""
    if viewer is not None and getattr(viewer, 'pk', None) == owner.pk:
        return True
    return _allowed(owner.counts_privacy, bool(getattr(viewer, 'pk', None)) and is_close(owner, viewer))


# ---------- профили разделов («маски») ----------

BOARD, SPACES = 'board', 'spaces'
_NO_PERSONA = '-'


def persona_of(user, section: str):
    """Маска человека в разделе или None. Из кеша — спрашивают на каждую карточку и сообщение."""
    from .models import Persona
    if user is None or not getattr(user, 'pk', None):
        return None
    key = f'persona:{user.pk}:{section}'
    row = cache.get(key)
    if row is None:
        p = Persona.objects.filter(user=user, section=section).first()
        row = {'name': p.name, 'avatar': p.avatar.url if p.avatar else '', 'link_main': p.link_main} if p else _NO_PERSONA
        cache.set(key, row, 3600)
    return None if row == _NO_PERSONA else row


def face(user, section: str = BOARD) -> dict:
    """Как показать человека в разделе: имя, аватар и можно ли вести в основной профиль.
    Без маски — обычный профиль. С маской — её имя и аватар; ссылка на основной профиль только если человек её оставил."""
    from django.urls import reverse
    if user is None:
        return {'name': str(_('Удалённый аккаунт')), 'avatar': '', 'link': '', 'id': None, 'masked': False, 'verified': False}
    p = persona_of(user, section)
    if p is None:
        return {'name': user.get_display_name(), 'avatar': user.avatar.url if user.avatar else '',
                'link': reverse('accounts:public', args=[user.pk]), 'id': user.pk, 'masked': False,
                'verified': user.platform_verified}
    open_ = p['link_main']
    return {'name': p['name'], 'avatar': p['avatar'], 'link': reverse('accounts:public', args=[user.pk]) if open_ else '',
            'id': user.pk if open_ else None, 'masked': True, 'verified': user.platform_verified and open_}


def personas(user) -> dict:
    """Маски человека для экрана «Мои профили»: {раздел: {'name', 'avatar', 'link_main'} | None}."""
    return {BOARD: persona_of(user, BOARD), SPACES: persona_of(user, SPACES)}


def save_persona(user, section: str, name: str, link_main: bool = True, avatar=None, clear_avatar: bool = False):
    """Создать или изменить маску. Одна на раздел; пустое имя — убрать маску (вернуться к основному профилю)."""
    from apps.core.uploads import clean_image

    from .models import Persona
    if section not in (BOARD, SPACES):
        raise PeopleError(_('Такого раздела нет.'), 404)
    name = ' '.join((name or '').split())[:40]
    if not name:
        delete_persona(user, section)
        return None
    if len(name) < 2:
        raise PeopleError(_('Имя слишком короткое — от 2 знаков.'))
    low = name.casefold()
    if not user.is_staff and any(x in low for x in ('ilm4', 'админ', 'admin', 'поддержк', 'support', 'модератор', 'moderator')):
        raise PeopleError(_('Это имя могут принять за сотрудника ilm4 — выберите другое.'))
    p, _created = Persona.objects.get_or_create(user=user, section=section, defaults={'name': name})
    p.name, p.link_main = name, bool(link_main)
    if clear_avatar and p.avatar:
        p.avatar.delete(save=False)
        p.avatar = ''
    if avatar:
        try:
            cleaned = clean_image(avatar)
        except Exception as exc:
            raise PeopleError(' '.join(getattr(exc, 'messages', [str(exc)]))) from exc
        if p.avatar:
            p.avatar.delete(save=False)
        p.avatar = cleaned
    p.save()
    cache.delete(f'persona:{user.pk}:{section}')
    return p


def delete_persona(user, section: str) -> None:
    from .models import Persona
    for p in Persona.objects.filter(user=user, section=section):
        if p.avatar:
            p.avatar.delete(save=False)
        p.delete()
    cache.delete(f'persona:{user.pk}:{section}')


def forward_link(owner, viewer=None) -> bool:
    """Показывать ли ссылку на профиль в «Переслано от …» (иначе — только имя, как в Telegram)."""
    return owner.forward_privacy == User.ALL


# ---------- фото профиля: несколько, как в Telegram ----------

def photos(user) -> list:
    """Фото профиля, новое первым. У старых аккаунтов история начинается с текущего аватара."""
    from .models import ProfilePhoto
    rows = list(ProfilePhoto.objects.filter(user=user)[:ProfilePhoto.MAX])
    if not rows and user.avatar:
        rows = [ProfilePhoto.objects.create(user=user, image=user.avatar.name)]
    return rows


def add_photo(user, image_name: str) -> None:
    """Новый аватар сохранён в user.avatar — добавить его в историю (прежние остаются, их можно листать)."""
    from .models import ProfilePhoto
    if not image_name:
        return
    if not ProfilePhoto.objects.filter(user=user, image=image_name).exists():
        ProfilePhoto.objects.create(user=user, image=image_name)
    else:                                              # вернул прежнее фото главным — оно снова первое
        ProfilePhoto.objects.filter(user=user, image=image_name).update(created_at=timezone.now())
    old = list(ProfilePhoto.objects.filter(user=user)[ProfilePhoto.MAX:])
    for ph in old:
        _drop_photo(ph)


def _drop_photo(photo) -> None:
    name = photo.image.name
    photo.delete()
    from .models import ProfilePhoto
    if name and not ProfilePhoto.objects.filter(image=name).exists() and not User.objects.filter(avatar=name).exists():
        photo.image.storage.delete(name)


def set_main_photo(user, photo_id) -> None:
    from .models import ProfilePhoto
    ph = ProfilePhoto.objects.filter(user=user, pk=photo_id).first()
    if ph is None:
        raise PeopleError(_('Фото не найдено'), 404)
    user.avatar = ph.image.name
    user.save(update_fields=['avatar'])               # сигнал поднимет это фото первым в списке


def delete_photo(user, photo_id) -> None:
    """Удалить фото; если это было главное — главным становится следующее (или аватара не будет)."""
    from .models import ProfilePhoto
    ph = ProfilePhoto.objects.filter(user=user, pk=photo_id).first()
    if ph is None:
        raise PeopleError(_('Фото не найдено'), 404)
    was_main = user.avatar and user.avatar.name == ph.image.name
    if was_main:
        nxt = ProfilePhoto.objects.filter(user=user).exclude(pk=ph.pk).first()
        user.avatar = nxt.image.name if nxt else None
        user.save(update_fields=['avatar'])
    _drop_photo(ph)


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


AT_KINDS = {'telegram', 'instagram', 'tiktok', 'x', 'github', 'threads', 'youtube'}      # где принято писать @имя
LINKS_VIEWS = ('auto', 'pills', 'icons', 'list')
LINK_PILLS = 4                         # сколько ссылок-пилюль видно сразу; остальные — за «ещё N»


def link_show(kind: str, value: str) -> str:
    """Как показать ссылку в профиле: имя в сетях с никами — с «@»; адрес сайта — без «https://»."""
    v = (value or '').strip()
    low = v.lower()
    if low.startswith(('http://', 'https://')):
        return v.split('://', 1)[1].rstrip('/')
    if kind in AT_KINDS and v and not v.startswith('@') and ' ' not in v and '/' not in v:
        return '@' + v
    return v


def links_view(person, count: int) -> str:
    """Вид ссылок в профиле: 'pills' — пилюли «значок + имя» (первые LINK_PILLS, остальные за «ещё N» — так делает
    Instagram), 'icons' — одни значки в ряд, 'list' — строками. Человек выбирает сам; «авто» — пилюли, если ссылок больше двух."""
    mode = (getattr(person, 'ui', None) or {}).get('links_view', 'auto')
    if mode in ('pills', 'icons', 'list'):
        return mode
    return 'pills' if count > 2 else 'list'


def set_links_view(user, mode: str) -> None:
    if mode not in LINKS_VIEWS:
        return
    ui = dict(user.ui or {})
    if ui.get('links_view', 'auto') != mode:
        ui['links_view'] = mode
        user.ui = ui
        user.save(update_fields=['ui'])


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
                    'show': link_show(x.kind, x.value), 'url': link_url(x.kind, x.value)}
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


# ---------- контакты (как в Telegram: «Контакты» → «Добавить контакт») ----------

MAX_CONTACTS = 2000


def saved_contacts(viewer) -> list:
    """Сохранённые контакты: [(человек, имя как записал я)], по алфавиту."""
    from .models import Contact
    blocked = UserBlock.ids_for(viewer)
    rows = (Contact.objects.filter(owner=viewer, friend__is_active=True).exclude(friend__in=blocked).select_related('friend'))
    out = [(c.friend, c.name) for c in rows]
    out.sort(key=lambda x: x[1].casefold())
    return out


def alias_map(viewer) -> dict:
    """Имена, под которыми человек записал свои контакты: {id человека: имя}. Как в Telegram — в чатах видно «как записал я»."""
    from .models import Contact
    if not getattr(viewer, 'pk', None):
        return {}
    key = f'contacts:alias:{viewer.pk}'
    out = cache.get(key)
    if out is None:
        out = {}
        for friend_id, first, last in Contact.objects.filter(owner=viewer).values_list('friend_id', 'first_name', 'last_name'):
            name = ' '.join(x for x in (first, last) if x)
            if name:
                out[friend_id] = name
        cache.set(key, out, 600)
    return out


def shown_name(person, viewer=None) -> str:
    """Имя человека для этого зрителя: как он записан в его контактах, иначе — имя из профиля."""
    if person is None:
        return str(_('Удалённый аккаунт'))
    return alias_map(viewer).get(person.pk) or person.get_display_name()


def is_contact(viewer, person) -> bool:
    from .models import Contact
    return bool(getattr(viewer, 'pk', None)) and Contact.objects.filter(owner=viewer, friend=person).exists()


def add_contact(viewer, phone: str = '', person=None, first_name: str = '', last_name: str = ''):
    """Добавить контакт по номеру (как «Добавить контакт» в Telegram) или из профиля человека.
    По номеру находится только тот, кто подтвердил номер и разрешил находить себя; сам номер нигде не показывается."""
    from .models import Contact
    if person is None:
        number = digits(phone)
        if len(number) < 9:
            raise PeopleError(_('Введите номер телефона целиком, с кодом страны.'))
        found = search(viewer, '+' + number, limit=1)
        if not found:
            raise PeopleError(_('Этого человека пока нет в ilm4 — или он запретил находить себя по номеру. Пригласите его ссылкой.'), 404)
        person = found[0]
    if person.pk == viewer.pk:
        raise PeopleError(_('Это ваш собственный аккаунт.'))
    if UserBlock.between(viewer, person):
        raise PeopleError(_('Недоступно: один из вас заблокировал другого.'), 403)
    if Contact.objects.filter(owner=viewer).count() >= MAX_CONTACTS:
        raise PeopleError(_('Слишком много контактов.'), 409)
    contact, _new = Contact.objects.update_or_create(owner=viewer, friend=person, defaults={
        'first_name': ' '.join((first_name or '').split())[:60], 'last_name': ' '.join((last_name or '').split())[:60]})
    cache.delete(f'contacts:alias:{viewer.pk}')
    return contact


def remove_contact(viewer, person) -> None:
    from .models import Contact
    Contact.objects.filter(owner=viewer, friend=person).delete()
    cache.delete(f'contacts:alias:{viewer.pk}')


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
    if viewer.is_staff:
        return
    from . import phone_verify
    if viewer.phone_verified or not phone_verify.available():
        return _hit(f'new_chats:{viewer.pk}', NEW_CHATS_PER_DAY, 86400)
    try:                                               # номер не подтверждён: пачка свежих аккаунтов не станет рассылкой
        _hit(f'new_chats:{viewer.pk}', NEW_CHATS_NO_PHONE, 86400)
    except PeopleError:
        raise PeopleError(_('Без подтверждённого номера можно начать не больше {n} новых диалогов в день. '
                            'Подтвердите номер в настройках — и ограничение снимется.').format(n=NEW_CHATS_NO_PHONE), 429) from None
