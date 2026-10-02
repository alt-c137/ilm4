"""API: люди — поиск по @имени и номеру, профиль «как в Telegram», близкие друзья, начало диалога."""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from apps.accounts import people
from apps.accounts.models import UserBlock
from apps.chat import services
from apps.chat.services import ChatError

from .base import ApiError, api, file_url, module_on

User = get_user_model()


def person_card(request, u, viewer=None) -> dict:
    """Строка в списке: поиск, контакты, близкие друзья."""
    viewer = viewer or request.user
    return {'id': u.pk, 'name': u.get_display_name(), 'handle': u.handle or '', 'avatar': file_url(request, u.avatar),
            'city': u.city, 'verified': u.platform_verified, 'online': people.quick_online(u, viewer)}


@api(methods=('POST',), auth=True)
def ping(request):
    """Приложение открыто — человек «в сети» (сама отметка ставится в декораторе api)."""
    return {'ok': True}


@api(auth=True, module='chat')
def people_list(request):
    """?q= — поиск по @имени или номеру; без q — «контакты» (с кем уже есть диалоги)."""
    q = request.GET.get('q', '').strip()
    me = request.user
    known = people.contacts(me)
    if not q:
        return {'items': [], 'contacts': [person_card(request, u) for u in known], 'hint': ''}
    try:
        found = people.search(me, q)
    except people.PeopleError as exc:
        raise ApiError(exc.message, exc.status) from exc
    low = q.lstrip('@').lower()
    mine = [u for u in known if low in f'{u.get_display_name()} {u.handle or ""}'.lower()]
    ids = {u.pk for u in found}
    hint = ''
    if not found and not mine:
        hint = _('Никого не нашли. Ищите по имени пользователя (@имя) или по номеру телефона целиком — '
                 'находятся те, кто разрешил искать себя по номеру.')
    return {'items': [person_card(request, u) for u in found],
            'contacts': [person_card(request, u) for u in mine if u.pk not in ids], 'hint': hint}


def _person(pk):
    return get_object_or_404(User, pk=pk, is_active=True)


def _pubs(request, person) -> list:
    """Публикации человека на площадке (объявления, вакансии, услуги…) — вкладка профиля."""
    from .base import MODULE_OF
    from .views_content import _REQ, KINDS, _qs, card
    _REQ.set(request)
    out = []
    for key, k in KINDS.items():
        if not k.owner or key in ('topics',) or not module_on(MODULE_OF[key]):
            continue
        for o in _qs(k).filter(**{k.owner: person}).order_by('-pk')[:6]:
            out.append(card(request, key, k, o))
    out.sort(key=lambda x: x['created_at'], reverse=True)
    return out[:24]


@api(auth=True)
def user(request, pk):
    """Профиль человека — ровно то, что он разрешил видеть тому, кто смотрит."""
    person, me = _person(pk), request.user
    mine = person.pk == me.pk
    close = people.is_close(person, me)             # я у него в близких — вижу то, что он показывает близким
    thread = None if mine else services.direct_between(me, person)
    return {
        'id': person.pk, 'me': mine, 'name': person.get_display_name(), 'handle': person.handle or '',
        'bio': person.bio, 'city': person.city, 'avatar': file_url(request, person.avatar),
        'verified': person.platform_verified, 'joined': person.date_joined.date().isoformat(),
        'presence': people.presence(person, me, close),
        'phone': people.phone_for(person, me, close),
        'links': people.links_for(person, me, close),
        'close': (not mine) and people.is_close(me, person),     # он у меня в близких друзьях
        'blocked': (not mine) and UserBlock.objects.filter(blocker=me, blocked=person).exists(),
        'blocked_any': (not mine) and UserBlock.between(me, person),
        'thread': thread.pk if thread else None,
        'muted': bool(thread and services.is_muted(thread, me)),
        'chat': module_on('chat') and not mine,
        'features': {k: v for k, v in services.flags(thread).items() if k in ('calls', 'video_calls')} if module_on('chat') else {},
        'pubs': _pubs(request, person),
    }


@api(methods=('POST',), auth=True, module='chat')
def user_chat(request, pk):
    """Открыть личный диалог с человеком (найти или создать)."""
    person, me = _person(pk), request.user
    if person.pk == me.pk:
        raise ApiError(_('Это вы сами.'))
    try:
        if services.direct_between(me, person) is None:
            people.check_new_chat(me, person)
        thread = services.open_direct(me, person)
    except (ChatError, people.PeopleError) as exc:
        raise ApiError(exc.message, exc.status) from exc
    return {'thread': thread.pk}


@api(methods=('POST',), auth=True)
def user_close(request, pk):
    """Добавить в близкие друзья / убрать: {'on': true|false}."""
    person = _person(pk)
    try:
        on = people.set_close(request.user, person, str(request.data.get('on', '1')).lower() in ('1', 'true', 'on'))
    except people.PeopleError as exc:
        raise ApiError(exc.message, exc.status) from exc
    return {'close': on}


@api(auth=True)
def close_friends(request):
    return {'items': [person_card(request, u) for u in people.close_friends(request.user)]}


@api(methods=('POST',), auth=True)
def my_links(request):
    """Соцсети профиля целиком: {'links': [{'kind', 'value', 'privacy'}, …]}."""
    rows = request.data.get('links', [])
    if not isinstance(rows, list):
        raise ApiError('links')
    try:
        people.set_links(request.user, rows)
    except people.PeopleError as exc:
        raise ApiError(exc.message, exc.status) from exc
    return {'links': people.links_for(request.user, request.user)}
