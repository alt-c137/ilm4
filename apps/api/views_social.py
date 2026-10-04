"""API ленты для приложения: «Для вас» / «Подписки», записи, лайки, комментарии, подписки, сторис, подарки.
Правила — в apps/social/services.py (те же, что на сайте)."""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from apps.social import services
from apps.social.services import SocialError

from .base import ApiError, abs_url, api, as_int, file_url

User = get_user_model()


def _fix(request, x: dict) -> dict:
    """Адреса — полные; фото постов канала — через API (с проверкой доступа по токену)."""
    def person(a):
        if a and a.get('avatar'):
            a = {**a, 'avatar': abs_url(request, a['avatar'])}
        return a
    x = {**x, 'author': person(x.get('author')), 'created': x['created'].isoformat(),
         'images': [{'url': abs_url(request, f"/api/v1/chat/file/{im['chat']}/") if im.get('chat') else abs_url(request, im['url']),
                     'auth': bool(im.get('chat'))} for im in x.get('images', [])],
         'web': abs_url(request, x['url'])}
    if x.get('repost'):
        r = x['repost']
        x['repost'] = {**r, 'author': person(r['author']), 'created': r['created'].isoformat(),
                       'images': [{'url': abs_url(request, im['url'])} for im in r['images']]}
    return x


def _wrap(fn):
    try:
        return fn()
    except SocialError as exc:
        raise ApiError(exc.message, exc.status) from exc


@api(auth=False, module='feed')
def feed(request):
    tab = request.GET.get('tab', 'for_you')
    data = services.feed(request.user, tab if tab in ('for_you', 'following') else 'for_you', before=request.GET.get('before') or None)
    from apps.core import ads
    ad = ads.pick('feed') if len(data['items']) >= 3 and not request.GET.get('before') else None
    if ad:
        ad = {**ad, 'image': abs_url(request, ad['image']) if ad['image'] else '', 'url': abs_url(request, ad['url'])}
    return {'items': [_fix(request, x) for x in data['items']], 'next': data['next'], 'ad': ad,
            'stories': services.module_on('stories'), 'shorts': services.module_on('shorts')}


@api(auth=True, module='feed')
def wall(request, user_id):
    person = get_object_or_404(User, pk=user_id, is_active=True)
    rows = [services.post_item(p, request.user) for p in services.wall(person, request.user, request.GET.get('before') or None)]
    services.decorate(rows, request.user)
    state = services.follow_state(request.user, person)
    return {'items': [_fix(request, x) for x in rows], 'following': state == 'on', 'requested': state == 'requested',
            'private': person.is_private, 'locked': not services.can_see_wall(person, request.user),
            **services.counts(person, request.user)}


@api(methods=('POST',), auth=True, module='feed')
def post_new(request):
    d = request.data
    post = _wrap(lambda: services.create_post(request.user, str(d.get('text', '')), request.FILES.getlist('photos'),
                                              str(d.get('privacy', 'all')), repost_of=as_int(d.get('repost_of')) or None))
    item = services.post_item(post, request.user)
    services.decorate([item], request.user)
    return _fix(request, item)


@api(methods=('POST',), auth=True, module='feed')
def post_act(request, pk, action):
    if action == 'delete':
        _wrap(lambda: services.delete_post(request.user, pk))
        return {'ok': True}
    if action == 'edit':
        post = _wrap(lambda: services.edit_post(request.user, pk, str(request.data.get('text', ''))))
        item = services.post_item(post, request.user)
        services.decorate([item], request.user)
        return _fix(request, item)
    raise ApiError('action', 404)


@api(methods=('POST',), auth=True, module='feed')
def like(request):
    return _wrap(lambda: services.like(request.user, str(request.data.get('target', ''))))


def _comment(request, c) -> dict:
    return {'id': c.pk, 'text': c.text, 'created': c.created_at.isoformat(), 'hue': c.user_id % 7,
            'user': {'id': c.user_id, 'name': c.user.get_display_name(), 'avatar': abs_url(request, c.user.avatar.url) if c.user.avatar else ''},
            'reply_to': c.reply_to.user.get_display_name() if c.reply_to_id and c.reply_to else '',
            'mine': c.user_id == request.user.pk}


@api(methods=('GET', 'POST'), auth=True, module='feed')
def comments(request):
    target = str(request.data.get('target') or request.GET.get('target', ''))
    if request.method == 'POST':
        _wrap(lambda: services.add_comment(request.user, target, str(request.data.get('text', '')),
                                           as_int(request.data.get('reply_to')) or None))
    rows = _wrap(lambda: services.comments_for(request.user, target))
    return {'items': [_comment(request, c) for c in rows]}


@api(methods=('POST',), auth=True, module='feed')
def comment_delete(request, pk):
    _wrap(lambda: services.delete_comment(request.user, pk))
    return {'ok': True}


@api(methods=('POST',), auth=True, module='feed')
def follow(request, user_id):
    person = get_object_or_404(User, pk=user_id, is_active=True)
    on = str(request.data.get('on', '1')).lower() in ('1', 'true', 'on')
    _wrap(lambda: services.follow(request.user, person, on))
    state = services.follow_state(request.user, person)
    return {'following': state == 'on', 'requested': state == 'requested', **services.counts(person, request.user)}


@api(methods=('GET', 'POST'), auth=True, module='feed')
def follow_requests(request):
    """Заявки в подписчики закрытого профиля. POST {user, ok} — одобрить или отклонить."""
    if request.method == 'POST':
        services.answer_request(request.user, as_int(request.data.get('user')), str(request.data.get('ok', '1')).lower() in ('1', 'true', 'on'))
    return {'items': [{'id': u.pk, 'name': u.get_display_name(), 'handle': u.handle or '', 'avatar': file_url(request, u.avatar)}
                      for u in services.follow_requests(request.user)]}


@api(auth=True, module='story')
def stories(request):
    rows = services.stories_for(request.user)
    for g in rows:
        g['author'] = {**g['author'], 'avatar': abs_url(request, g['author']['avatar']) if g['author']['avatar'] else ''}
        for s in g['items']:
            s['url'], s['created'] = abs_url(request, s['url']), s['created'].isoformat()
    return {'items': rows}


@api(methods=('POST',), auth=True, module='story')
def story_new(request):
    s = _wrap(lambda: services.add_story(request.user, request.FILES.get('photo'), str(request.data.get('caption', '')),
                                         str(request.data.get('privacy', 'all'))))
    return {'id': s.pk}


@api(methods=('POST',), auth=True, module='story')
def story_act(request, pk, action):
    if action == 'view':
        _wrap(lambda: services.view_story(request.user, pk, str(request.data.get('reaction', ''))))
    elif action == 'delete':
        _wrap(lambda: services.delete_story(request.user, pk))
    elif action == 'viewers':
        rows = _wrap(lambda: services.story_viewers(request.user, pk))
        return {'items': [{'name': v['user']['name'], 'id': v['user']['id'], 'reaction': v['reaction']} for v in rows]}
    else:
        raise ApiError('action', 404)
    return {'ok': True}


@api(auth=True, module='gifts')
def gifts(request):
    return {'items': [{'id': g.pk, 'title': g.title, 'emoji': g.emoji, 'price': g.price,
                       'image': abs_url(request, g.image.url) if g.image else ''} for g in services.gift_catalog()]}


@api(methods=('POST',), auth=True, module='gifts')
def gift_send(request, user_id):
    person = get_object_or_404(User, pk=user_id, is_active=True)
    d = request.data
    _wrap(lambda: services.send_gift(request.user, person, as_int(d.get('gift')), str(d.get('message', '')), bool(d.get('anonymous'))))
    return {'ok': True}


@api(methods=('POST',), auth=True, module='feed')
def save(request):
    """«Сохранить» карточку ленты / убрать: {target} → {saved}."""
    return _wrap(lambda: services.save(request.user, str(request.data.get('target', ''))))


@api(auth=True, module='feed')
def saved(request):
    """Сохранённое: записи целиком, остальное — {brief: true, title, text, web}."""
    out = []
    for x in services.saved_items(request.user):
        out.append({**x, 'web': abs_url(request, x['web'])} if x.get('brief') else _fix(request, x))
    return {'items': out}


@api(methods=('POST',))
def metrics(request):
    """Время по экранам приложения: {items: [{s: раздел, t: секунды, o: 1 — открыл}]} (до 20 строк за раз)."""
    from apps.metrics import services as metrics_services
    from apps.metrics.models import Use
    if request.user.is_authenticated:
        for row in (request.data.get('items') or [])[:20]:
            if isinstance(row, dict):
                metrics_services.record(request.user, '', str(row.get('s', '')), row.get('t'), row.get('o'), platform=Use.APP)
    return {'ok': True}
