"""Лента, записи, подписки, лайки, комментарии, сторис, короткие видео, подарки — правила в одном месте.

Сайт (views.py) и приложение (apps/api/views_social.py) зовут только эти функции.

Лента — как во ВКонтакте, но из всего, что есть на ilm4:
* «Для вас» — записи людей, посты ваших каналов и свежие публикации разделов (объявления, новости, вакансии,
  места, попутчики, вопросы на форуме);
* «Подписки» — только записи тех, на кого вы подписаны, посты ваших каналов и ваши собственные записи.
Листается без конца: курсор — время последней показанной карточки.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, F, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _

from .models import ALL, CLOSE, Comment, Follow, Gift, Like, Post, PostPhoto, Saved, Short, Story, StoryView, UserGift

PAGE = 20
POSTS_PER_DAY = 30
COMMENTS_PER_HOUR = 60
STORIES_PER_DAY = 30


class SocialError(Exception):
    def __init__(self, message, status=400):
        super().__init__(str(message))
        self.message, self.status = str(message), status


def module_on(key: str) -> bool:
    from apps.core.models import ModuleConfig
    return ModuleConfig.objects.filter(key=key, status=ModuleConfig.ON).exists()


def _limit(key: str, n: int, seconds: int, text: str) -> None:
    from django.core.cache import cache
    hits = cache.get(key, 0)
    if hits >= n:
        raise SocialError(text, 429)
    cache.set(key, hits + 1, seconds)


def _blocked_ids(viewer) -> set:
    from apps.accounts.models import UserBlock
    return set(UserBlock.ids_for(viewer)) if getattr(viewer, 'pk', None) else set()


def _close_of(viewer) -> set:
    """Чьи записи «для близких друзей» видит этот человек (у кого он в близких)."""
    from apps.accounts.models import CloseFriend
    if not getattr(viewer, 'pk', None):
        return set()
    return set(CloseFriend.objects.filter(friend=viewer).values_list('owner_id', flat=True))


def visible_posts(viewer):
    """Записи, которые видит человек: открытые всем, «близким» — если он в близких у автора, и свои."""
    qs = Post.objects.filter(hidden=False).select_related('author', 'repost_of__author').prefetch_related('photos')
    # закрытый профиль: записи видят только одобренные подписчики (и сам автор)
    if not getattr(viewer, 'pk', None):
        return qs.filter(privacy=ALL, author__is_private=False)
    approved = Follow.objects.filter(follower=viewer, approved=True).values('author_id')
    return (qs.filter(Q(privacy=ALL) | Q(author=viewer) | Q(privacy=CLOSE, author__in=_close_of(viewer)))
            .filter(Q(author__is_private=False) | Q(author=viewer) | Q(author__in=approved))
            .exclude(author__in=_blocked_ids(viewer)))


# ---------- записи ----------

def create_post(user, text: str, photos=(), privacy: str = ALL, repost_of=None) -> Post:
    """Новая запись на стене. Фото проверяются и пересохраняются (без геометок)."""
    from apps.core.uploads import clean_image
    text = (text or '').strip()[:Post.MAX_TEXT]
    photos = [p for p in (photos or []) if p][:Post.MAX_PHOTOS]
    original = None
    if repost_of:
        original = visible_posts(user).filter(pk=repost_of).first()
        if original is None:
            raise SocialError(_('Запись не найдена'), 404)
        original = original.repost_of or original           # репост репоста — ссылается на оригинал
    if not text and not photos and original is None:
        raise SocialError(_('Напишите что-нибудь или добавьте фото.'))
    _limit(f'posts:{user.pk}:{timezone.localdate()}', POSTS_PER_DAY, 86400,
           _('Сегодня вы уже опубликовали много записей. Попробуйте завтра.'))
    cleaned = []
    for p in photos:
        try:
            cleaned.append(clean_image(p))
        except Exception as exc:                          # ValidationError из clean_image — понятный текст
            raise SocialError(' '.join(getattr(exc, 'messages', [str(exc)]))) from exc
    with transaction.atomic():
        post = Post.objects.create(author=user, text=text, privacy=privacy if privacy in (ALL, CLOSE) else ALL,
                                   repost_of=original)
        for i, img in enumerate(cleaned):
            PostPhoto.objects.create(post=post, image=img, order=i)
        if original is not None:
            Post.objects.filter(pk=original.pk).update(reposts=F('reposts') + 1)
    return post


def edit_post(user, post_id, text: str) -> Post:
    post = Post.objects.filter(pk=post_id, author=user).first()
    if post is None:
        raise SocialError(_('Запись не найдена'), 404)
    text = (text or '').strip()[:Post.MAX_TEXT]
    if not text and not post.photos.exists() and not post.repost_of_id:
        raise SocialError(_('Напишите что-нибудь или добавьте фото.'))
    post.text, post.edited_at = text, timezone.now()
    post.save(update_fields=['text', 'edited_at'])
    return post


def delete_post(user, post_id) -> None:
    post = Post.objects.filter(pk=post_id).first()
    if post is None or (post.author_id != user.pk and not user.is_staff):
        raise SocialError(_('Запись не найдена'), 404)
    for ph in post.photos.all():
        ph.image.delete(save=False)
    if post.repost_of_id:
        Post.objects.filter(pk=post.repost_of_id, reposts__gt=0).update(reposts=F('reposts') - 1)
    Like.objects.filter(target=post.key).delete()
    Comment.objects.filter(target=post.key).delete()
    post.delete()


def wall(author, viewer, before=None, limit: int = PAGE) -> list:
    qs = visible_posts(viewer).filter(author=author)
    if before:
        qs = qs.filter(created_at__lt=before)
    return list(qs[:limit])


# ---------- подписки ----------

def follow(user, author, on: bool = True) -> bool:
    if author.pk == user.pk:
        raise SocialError(_('Это вы сами.'))
    if on:
        if author.pk in _blocked_ids(user):
            raise SocialError(_('Недоступно: один из вас заблокировал другого.'), 403)
        # закрытый профиль: подписка становится заявкой, пока автор её не одобрит (как в Instagram и ВК)
        row, created = Follow.objects.get_or_create(follower=user, author=author, defaults={'approved': not author.is_private})
        if created and not row.approved:
            _notify_request(author, user)
    else:
        Follow.objects.filter(follower=user, author=author).delete()
    return on


def _notify_request(author, follower) -> None:
    from django.conf import settings
    from django.utils import translation

    from apps.core.models import Notification
    with translation.override(author.language or settings.LANGUAGE_CODE):      # на языке получателя
        text = str(_('{name} хочет подписаться на вас').format(name=follower.get_display_name()))
    Notification.objects.create(user=author, text=text, url='/feed/requests/')


def is_following(user, author) -> bool:
    return bool(getattr(user, 'pk', None)) and Follow.objects.filter(follower=user, author=author, approved=True).exists()


def follow_state(user, author) -> str:
    """'on' — подписан, 'requested' — заявка ждёт ответа, '' — нет."""
    if not getattr(user, 'pk', None):
        return ''
    row = Follow.objects.filter(follower=user, author=author).values_list('approved', flat=True).first()
    return '' if row is None else ('on' if row else 'requested')


def can_see_wall(author, viewer) -> bool:
    """Открыта ли стена этому человеку: закрытый профиль показывает записи только одобренным подписчикам."""
    if not author.is_private or getattr(viewer, 'pk', None) == author.pk:
        return True
    return is_following(viewer, author)


def follow_requests(user) -> list:
    """Заявки в подписчики закрытого профиля: [человек, …], новые сверху."""
    rows = Follow.objects.filter(author=user, approved=False).select_related('follower').order_by('-created_at')[:200]
    return [r.follower for r in rows if r.follower.is_active]


def answer_request(user, follower_id, ok: bool) -> None:
    qs = Follow.objects.filter(author=user, follower_id=follower_id, approved=False)
    if ok:
        qs.update(approved=True)
    else:
        qs.delete()


def set_private(user, on: bool) -> None:
    """Закрыть или открыть профиль. Открыл — все ждавшие заявки становятся подписками."""
    on = bool(on)
    if user.is_private != on:
        user.is_private = on
        user.save(update_fields=['is_private'])
    if not on:
        Follow.objects.filter(author=user, approved=False).update(approved=True)


def counts(author, viewer=None) -> dict:
    """Счётчики профиля. Человек может скрыть их (Приватность → «Кто видит мои счётчики») — тогда counts_hidden."""
    from apps.accounts import people
    if not people.can_see_counts(author, viewer):
        return {'counts_hidden': True}
    return {'followers': Follow.objects.filter(author=author, approved=True).count(),
            'follows': Follow.objects.filter(follower=author, approved=True).count(),
            'posts': Post.objects.filter(author=author, hidden=False).count(), 'counts_hidden': False}


# ---------- лайки и комментарии (к любой карточке ленты) ----------

TARGETS = {'post', 'msg', 'buy', 'news', 'jobs', 'place', 'trip', 'topic', 'short'}


def _check_target(viewer, target: str) -> str:
    """'post:12' → проверить, что объект есть и человеку виден. Иначе по выдуманным ключам набирали бы лайки."""
    kind, _sep, pk = (target or '').partition(':')
    if kind not in TARGETS or not pk.isdigit():
        raise SocialError(_('Не найдено'), 404)
    pk = int(pk)
    ok = False
    if kind == 'post':
        ok = visible_posts(viewer).filter(pk=pk).exists()
    elif kind == 'msg':
        from apps.chat import services as chat
        from apps.chat.models import Message
        m = Message.objects.select_related('thread').filter(pk=pk, scheduled_at__isnull=True).first()
        ok = m is not None and m.thread.is_channel and chat.can_read(m.thread, viewer)
    elif kind == 'news':
        from apps.news.models import NewsPost
        ok = NewsPost.objects.filter(pk=pk).exists()
    elif kind == 'short':
        ok = Short.objects.filter(pk=pk, status=Short.APPROVED).exists()
    else:
        from apps.core.models import Moderation
        model = {'buy': 'market.Listing', 'jobs': 'jobs.Vacancy', 'place': 'maps.HalalPlace', 'trip': 'transport.Trip',
                 'topic': 'forum.Topic'}[kind]
        from django.apps import apps
        ok = apps.get_model(model).objects.filter(pk=pk, status=Moderation.APPROVED).exists()
    if not ok:
        raise SocialError(_('Не найдено'), 404)
    return f'{kind}:{pk}'


def like(user, target: str) -> dict:
    """Лайк / снять лайк. Возвращает {'liked', 'likes'}."""
    target = _check_target(user, target)
    obj, created = Like.objects.get_or_create(user=user, target=target)
    if not created:
        obj.delete()
    delta = 1 if created else -1
    kind, pk = target.split(':')
    if kind == 'post':
        Post.objects.filter(pk=pk).update(likes=F('likes') + delta)
    elif kind == 'short':
        Short.objects.filter(pk=pk).update(likes=F('likes') + delta)
    return {'liked': created, 'likes': Like.objects.filter(target=target).count()}


def save(user, target: str) -> dict:
    """«Сохранить» / убрать из сохранённого. Возвращает {'saved'}."""
    target = _check_target(user, target)
    obj, created = Saved.objects.get_or_create(user=user, target=target)
    if not created:
        obj.delete()
    return {'saved': created}


def saved_items(viewer, limit: int = 60) -> list:
    """Сохранённое: записи — целиком, остальное (объявления, новости, посты каналов) — строкой со ссылкой."""
    rows = list(Saved.objects.filter(user=viewer)[:limit])
    posts = {p.pk: p for p in visible_posts(viewer).filter(pk__in=[r.target.split(':')[1] for r in rows if r.target.startswith('post:')])}
    out = []
    for r in rows:
        kind, pk = r.target.split(':')
        if kind == 'post':
            if int(pk) in posts:
                out.append(post_item(posts[int(pk)], viewer))
            continue
        brief = _brief(kind, int(pk))
        if brief:
            out.append({'key': r.target, 'kind': kind, 'brief': True, **brief})
    decorate([x for x in out if not x.get('brief')], viewer)
    return out


def _brief(kind: str, pk: int) -> dict | None:
    """Коротко о карточке не из записей: заголовок и ссылка."""
    from django.urls import reverse
    if kind == 'msg':
        from apps.chat.models import Message
        m = Message.objects.filter(pk=pk).select_related('thread').first()
        return {'title': m.thread.title, 'text': m.body[:160], 'web': reverse('chat:thread', args=[m.thread_id]) + f'?at={m.pk}'} if m else None
    if kind == 'news':
        from apps.news.models import NewsPost
        n = NewsPost.objects.filter(pk=pk).first()
        return {'title': n.title, 'text': n.summary, 'web': f'/news/{n.slug}/'} if n else None
    from apps.core.publications import BY_KEY
    pub = BY_KEY.get({'place': 'map', 'trip': 'trips', 'topic': 'forum'}.get(kind, kind))
    if pub is None:
        return None
    obj = pub.get_model().objects.filter(pk=pk).first()
    return {'title': pub.title_of(obj), 'text': '', 'web': pub.url_of(obj)} if obj else None


def comments_for(viewer, target: str, limit: int = 300) -> list:
    target = _check_target(viewer, target)
    blocked = _blocked_ids(viewer)
    rows = list(Comment.objects.filter(target=target, hidden=False).exclude(user__in=blocked)
                .select_related('user', 'reply_to__user')[:limit])
    for c in rows:
        c.hue = c.user_id % 7
    return rows


def add_comment(user, target: str, text: str, reply_to=None) -> Comment:
    target = _check_target(user, target)
    text = (text or '').strip()[:Comment.MAX_TEXT]
    if not text:
        raise SocialError(_('Комментарий пустой.'))
    _limit(f'comments:{user.pk}', COMMENTS_PER_HOUR, 3600, _('Слишком много комментариев подряд. Подождите немного.'))
    parent = Comment.objects.filter(pk=reply_to, target=target).first() if reply_to else None
    c = Comment.objects.create(user=user, target=target, text=text, reply_to=parent)
    kind, pk = target.split(':')
    if kind == 'post':
        Post.objects.filter(pk=pk).update(comments=F('comments') + 1)
        author = Post.objects.filter(pk=pk).values_list('author_id', flat=True).first()
        _notify({author, parent.user_id if parent else None} - {user.pk, None}, user, text, f'/feed/post/{pk}/')
    elif parent and parent.user_id != user.pk:
        _notify({parent.user_id}, user, text, f'/feed/c/{target}/')
    return c


def _notify(user_ids, actor, text: str, url: str) -> None:
    from apps.core.models import Notification
    for uid in user_ids:
        Notification.objects.create(user_id=uid, url=url, text=f'{actor.get_display_name()}: {text[:80]}')


def delete_comment(user, comment_id) -> None:
    c = Comment.objects.filter(pk=comment_id).first()
    if c is None:
        raise SocialError(_('Не найдено'), 404)
    kind, pk = c.target.split(':')
    owner = Post.objects.filter(pk=pk).values_list('author_id', flat=True).first() if kind == 'post' else None
    if c.user_id != user.pk and owner != user.pk and not user.is_staff:     # автор записи может чистить комментарии
        raise SocialError(_('Нет доступа'), 403)
    c.delete()
    if kind == 'post':
        Post.objects.filter(pk=pk, comments__gt=0).update(comments=F('comments') - 1)


# ---------- лента ----------

def _person(u) -> dict:
    return {'id': u.pk, 'name': u.get_display_name(), 'avatar': u.avatar.url if u.avatar else '', 'handle': u.handle or '',
            'verified': u.platform_verified, 'url': reverse('accounts:public', args=[u.pk]), 'hue': u.pk % 7}


def _seller(u) -> dict:
    """Автор объявления или вакансии в ленте — с учётом его «маски» (профиля для объявлений)."""
    from apps.accounts import people
    f = people.face(u, people.BOARD)
    if not f['masked']:
        return _person(u)
    return {'id': f['id'], 'name': f['name'], 'avatar': f['avatar'], 'handle': '', 'verified': f['verified'],
            'url': f['link'], 'hue': len(f['name']) % 7}


def post_item(p: Post, viewer=None) -> dict:
    item = {'key': p.key, 'kind': 'post', 'label': '', 'id': p.pk, 'author': _person(p.author), 'title': '', 'text': p.text,
            'images': [{'url': ph.image.url} for ph in p.photos.all()], 'price': '', 'url': f'/feed/post/{p.pk}/',
            'created': p.created_at, 'privacy': p.privacy, 'edited': bool(p.edited_at),
            'mine': bool(viewer is not None and getattr(viewer, 'pk', None) == p.author_id), 'can_comment': True,
            'reposts': p.reposts, 'views': p.views, 'repost': None}
    if p.repost_of_id and p.repost_of:
        o = p.repost_of
        item['repost'] = {'id': o.pk, 'author': _person(o.author), 'text': o.text, 'created': o.created_at,
                          'images': [{'url': ph.image.url} for ph in o.photos.all()], 'url': f'/feed/post/{o.pk}/'}
    return item


def _channel_items(viewer, before, limit: int) -> list:
    """Посты каналов, на которые подписан человек."""
    from apps.chat.models import Member, Message, Thread
    if not getattr(viewer, 'pk', None):
        return []
    mine = Member.objects.filter(user=viewer, thread__kind=Thread.CHANNEL, thread__closed=False).exclude(role=Member.BANNED)
    qs = (Message.objects.filter(thread__in=mine.values('thread'), scheduled_at__isnull=True, comment_of__isnull=True)
          .exclude(kind=Message.SYSTEM).select_related('thread').order_by('-created_at'))
    if before:
        qs = qs.filter(created_at__lt=before)
    out = []
    for m in qs[:limit]:
        t = m.thread
        out.append({'key': f'msg:{m.pk}', 'kind': 'channel', 'label': _('Канал'), 'id': m.pk,
                    'author': {'room': t.pk, 'name': t.title, 'avatar': t.avatar.url if t.avatar else '', 'handle': t.handle or '',
                               'verified': t.platform_verified, 'url': reverse('chat:thread', args=[t.pk]), 'hue': t.pk % 7},
                    'title': '', 'text': m.body, 'price': '', 'url': reverse('chat:thread', args=[t.pk]) + f'?at={m.pk}',
                    'images': [{'url': reverse('chat:file', args=[m.pk]), 'chat': m.pk}] if m.kind == Message.PHOTO and m.attachment else [],
                    'created': m.created_at, 'views': m.views, 'can_comment': True, 'reposts': 0, 'repost': None,
                    'channel_comments': t.comments_on, 'comments_count': m.comments_count})
    return out


def _pub_items(viewer, before, limit: int) -> list:
    """Свежие публикации разделов — то, ради чего человек пришёл на ilm4."""
    from apps.core import money
    from apps.core.models import Moderation
    items = []

    def take(qs, field='created_at'):
        if before:
            qs = qs.filter(**{f'{field}__lt': before})
        return list(qs.order_by(f'-{field}')[:limit])

    if module_on('news'):
        from apps.news.models import NewsPost
        for p in take(NewsPost.objects.all()):
            items.append({'key': f'news:{p.pk}', 'kind': 'news', 'label': _('Новости'), 'id': p.pk, 'author': None,
                          'title': p.title, 'text': p.summary, 'images': [{'url': p.cover.url}] if p.cover else [],
                          'price': '', 'url': f'/news/{p.slug}/', 'created': p.created_at})
    if module_on('buy'):
        from apps.market.models import Listing
        for x in take(Listing.objects.filter(status=Moderation.APPROVED, is_active=True).select_related('owner')):
            items.append({'key': f'buy:{x.pk}', 'kind': 'buy', 'label': _('Маркет'), 'id': x.pk, 'author': _seller(x.owner),
                          'title': x.title, 'text': x.description[:300], 'images': [{'url': x.photo.url}] if x.photo else [],
                          'price': money.fmt(x.price, x.currency) if x.price else _('Даром'), 'url': reverse('market:detail', args=[x.pk]),
                          'created': x.created_at, 'city': x.city})
    if module_on('jobs'):
        from apps.jobs.models import Vacancy
        for v in take(Vacancy.objects.filter(status=Moderation.APPROVED).select_related('owner')):
            items.append({'key': f'jobs:{v.pk}', 'kind': 'jobs', 'label': _('Работа'), 'id': v.pk, 'author': _seller(v.owner),
                          'title': v.title, 'text': f'{v.company} · {v.city}', 'images': [], 'price': v.salary or '',
                          'url': reverse('jobs:detail', args=[v.pk]), 'created': v.created_at})
    if module_on('map'):
        from apps.maps.models import HalalPlace
        for p in take(HalalPlace.objects.filter(status=Moderation.APPROVED)):
            items.append({'key': f'place:{p.pk}', 'kind': 'place', 'label': str(p.get_category_display()), 'id': p.pk,
                          'author': None, 'title': p.name, 'text': (p.description or '')[:240] or p.city,
                          'images': [{'url': p.photo.url}] if p.photo else [], 'price': '',
                          'url': reverse('maps:detail', args=[p.pk]), 'created': p.created_at})
    if module_on('forum'):
        from apps.forum.models import Topic
        for tp in take(Topic.objects.filter(status=Moderation.APPROVED).select_related('author')):
            items.append({'key': f'topic:{tp.pk}', 'kind': 'topic', 'label': _('Вопрос'), 'id': tp.pk, 'author': _person(tp.author),
                          'title': tp.title, 'text': tp.body[:300], 'images': [], 'price': '',
                          'url': reverse('forum:detail', args=[tp.pk]), 'created': tp.created_at})
    if module_on('transport'):
        from apps.transport.models import Trip
        for tr in take(Trip.objects.filter(status=Moderation.APPROVED, is_active=True, departs_at__gt=timezone.now())
                       .select_related('owner')):
            items.append({'key': f'trip:{tr.pk}', 'kind': 'trip', 'label': _('Попутчики'), 'id': tr.pk, 'author': _person(tr.owner),
                          'title': f'{tr.from_city} → {tr.to_city}', 'text': (tr.comment or '')[:200],
                          'images': [], 'price': money.fmt(tr.price, tr.currency) if tr.price else '', 'url': reverse('transport:trip', args=[tr.pk]), 'created': tr.created_at})
    return items


def feed(viewer, tab: str = 'for_you', before=None, limit: int = PAGE) -> dict:
    """Страница ленты. before — ISO-время последней карточки прошлой страницы."""
    if isinstance(before, str):
        before = parse_datetime(before) if before else None
    blocked = _blocked_ids(viewer)
    posts = visible_posts(viewer)
    if tab == 'following':
        followed = list(Follow.objects.filter(follower=viewer, approved=True).values_list('author_id', flat=True)) if getattr(viewer, 'pk', None) else []
        posts = posts.filter(Q(author__in=followed) | Q(author=viewer))
    if before:
        posts = posts.filter(created_at__lt=before)
    items = [post_item(p, viewer) for p in posts[:limit]]
    items += _channel_items(viewer, before, limit)
    if tab != 'following':
        items += [x for x in _pub_items(viewer, before, max(4, limit // 3))
                  if not (x.get('author') and x['author'].get('id') in blocked)]
    items.sort(key=lambda x: x['created'], reverse=True)
    items = items[:limit]
    cursor = items[-1]['created'].isoformat() if len(items) >= limit else ''
    rank(items, viewer)
    decorate(items, viewer)
    return {'items': items, 'next': cursor}


# ---------- порядок ленты под человека ----------

def affinity(viewer) -> dict:
    """Что человеку интересно — по его же действиям: на кого подписан, чьи записи лайкал, какие виды карточек лайкал и сохранял."""
    from collections import Counter
    if not getattr(viewer, 'pk', None):
        return {'follows': set(), 'authors': Counter(), 'kinds': Counter()}
    follows = set(Follow.objects.filter(follower=viewer, approved=True).values_list('author_id', flat=True))
    targets = list(Like.objects.filter(user=viewer).order_by('-pk').values_list('target', flat=True)[:300])
    targets += list(Saved.objects.filter(user=viewer).order_by('-pk').values_list('target', flat=True)[:100]) * 2      # сохранил — сильнее лайка
    kinds = Counter(t.split(':', 1)[0] for t in targets)
    post_ids = [t.split(':', 1)[1] for t in targets if t.startswith('post:')]
    author_of = dict(Post.objects.filter(pk__in=post_ids).values_list('pk', 'author_id'))
    authors = Counter(author_of[int(pk)] for pk in post_ids if int(pk) in author_of)
    return {'follows': follows, 'authors': authors, 'kinds': kinds}


def rank(items, viewer) -> None:
    """Переставить карточки внутри страницы: свежесть + интерес человека. Подписки — выше всего (их записи не теряются),
    затем авторы и виды карточек, которые он лайкает и сохраняет. Гостю и новичку — просто по времени."""
    aff = affinity(viewer)
    if not aff['follows'] and not aff['kinds']:
        return
    total = sum(aff['kinds'].values()) or 1

    def boost(x) -> float:
        author = (x.get('author') or {}).get('id')
        hours = 0.0
        if author in aff['follows']:
            hours += 8
        hours += min(6, 2 * aff['authors'].get(author, 0))
        hours += 4 * aff['kinds'].get(x['kind'] if x['kind'] != 'channel' else 'msg', 0) / total
        return hours
    from datetime import timedelta
    items.sort(key=lambda x: x['created'] + timedelta(hours=boost(x)), reverse=True)


def decorate(items, viewer) -> None:
    """Лайки и комментарии разом для страницы ленты — фиксированным числом запросов."""
    keys = [x['key'] for x in items]
    likes = dict(Like.objects.filter(target__in=keys).values('target').annotate(n=Count('id')).values_list('target', 'n'))
    comments = dict(Comment.objects.filter(target__in=keys, hidden=False).values('target').annotate(n=Count('id'))
                    .values_list('target', 'n'))
    mine = set(Like.objects.filter(target__in=keys, user=viewer).values_list('target', flat=True)) if getattr(viewer, 'pk', None) else set()
    kept = set(Saved.objects.filter(target__in=keys, user=viewer).values_list('target', flat=True)) if getattr(viewer, 'pk', None) else set()
    for x in items:
        x['likes'], x['liked'] = likes.get(x['key'], 0), x['key'] in mine
        x['comments'], x['saved'] = comments.get(x['key'], 0), x['key'] in kept


# ---------- сторис (основа; раздел 'stories') ----------

def stories_for(viewer) -> list:
    """Лента сторис: сначала свои, затем тех, на кого подписан, и собеседников. [{author, items, seen}]."""
    if not getattr(viewer, 'pk', None):
        return []
    from apps.accounts import people
    now = timezone.now()
    authors = [viewer.pk] + list(Follow.objects.filter(follower=viewer, approved=True).values_list('author_id', flat=True)) \
        + [u.pk for u in people.contacts(viewer, limit=60)]
    close = _close_of(viewer)
    qs = (Story.objects.filter(author__in=set(authors), expires_at__gt=now).exclude(author__in=_blocked_ids(viewer))
          .filter(Q(privacy=ALL) | Q(author=viewer) | Q(author__in=close)).select_related('author'))
    seen = set(StoryView.objects.filter(user=viewer, story__in=qs).values_list('story_id', flat=True))
    groups = {}
    for s in qs:
        g = groups.setdefault(s.author_id, {'author': _person(s.author), 'items': [], 'seen': True, 'mine': s.author_id == viewer.pk})
        g['items'].append({'id': s.pk, 'kind': s.kind, 'url': s.media.url, 'caption': s.caption, 'created': s.created_at,
                           'seen': s.pk in seen})
        g['seen'] = g['seen'] and s.pk in seen
    rows = list(groups.values())
    rows.sort(key=lambda g: (not g['mine'], g['seen'], -max(i['created'].timestamp() for i in g['items'])))
    return rows


def add_story(user, upload, caption: str = '', privacy: str = ALL) -> Story:
    if not module_on('stories'):
        raise SocialError(_('Сторис скоро появятся.'), 403)
    from apps.core.uploads import clean_image
    _limit(f'stories:{user.pk}:{timezone.localdate()}', STORIES_PER_DAY, 86400, _('Сегодня вы уже выложили много сторис.'))
    try:
        image = clean_image(upload)
    except Exception as exc:
        raise SocialError(' '.join(getattr(exc, 'messages', [str(exc)]))) from exc
    if image is None:
        raise SocialError(_('Добавьте фото.'))
    return Story.objects.create(author=user, kind=Story.PHOTO, media=image, caption=(caption or '').strip()[:200],
                                privacy=privacy if privacy in (ALL, CLOSE) else ALL,
                                expires_at=timezone.now() + timedelta(hours=Story.HOURS))


def view_story(user, story_id, reaction: str = '') -> None:
    s = Story.objects.filter(pk=story_id, expires_at__gt=timezone.now()).first()
    if s is None:
        raise SocialError(_('Сторис уже исчезла.'), 404)
    if s.author_id == user.pk:
        return
    obj, created = StoryView.objects.get_or_create(story=s, user=user)
    if created:
        Story.objects.filter(pk=s.pk).update(views=F('views') + 1)
    if reaction:
        obj.reaction = reaction[:16]
        obj.save(update_fields=['reaction'])


def story_viewers(user, story_id) -> list:
    """Кто посмотрел сторис — видит только автор (как в Telegram)."""
    s = Story.objects.filter(pk=story_id, author=user).first()
    if s is None:
        raise SocialError(_('Не найдено'), 404)
    return [{'user': _person(v.user), 'reaction': v.reaction, 'at': v.at} for v in s.seen_by.select_related('user')]


def delete_story(user, story_id) -> None:
    s = Story.objects.filter(pk=story_id, author=user).first()
    if s is None:
        raise SocialError(_('Не найдено'), 404)
    s.media.delete(save=False)
    s.delete()


def purge_stories() -> int:
    """Удалить исчезнувшие сторис вместе с файлами (manage.py social_cleanup)."""
    n = 0
    for s in Story.objects.filter(expires_at__lte=timezone.now())[:500]:
        s.media.delete(save=False)
        s.delete()
        n += 1
    return n


# ---------- короткие видео и подарки (основа; разделы 'shorts' и 'gifts') ----------

def shorts(viewer, before_id: int = 0, limit: int = 10) -> list:
    qs = Short.objects.filter(status=Short.APPROVED).select_related('author').exclude(author__in=_blocked_ids(viewer))
    if before_id:
        qs = qs.filter(pk__lt=before_id)
    return list(qs.order_by('-pk')[:limit])


def add_short(user, video, caption: str = '', duration: int = 0) -> Short:
    """Короткое видео уходит на проверку модератором (как публикации разделов)."""
    if not module_on('shorts'):
        raise SocialError(_('Короткие видео скоро появятся.'), 403)
    if video is None:
        raise SocialError(_('Добавьте видео.'))
    from apps.chat.media import video_ext
    if not video_ext(video.read(16)):
        raise SocialError(_('Неподдерживаемый формат файла'))
    video.seek(0)
    if duration > Short.MAX_SECONDS:
        raise SocialError(_('Короткое видео — до {v1} секунд.').format(v1=Short.MAX_SECONDS))
    return Short.objects.create(author=user, video=video, caption=(caption or '').strip()[:500], duration=max(0, int(duration or 0)))


def gift_catalog() -> list:
    return list(Gift.objects.filter(active=True))


def send_gift(user, receiver, gift_id, message: str = '', anonymous: bool = False) -> UserGift:
    """Подарок другому человеку. Платные подарки списываются с кошелька — подключатся вместе с разделом 'gifts'."""
    if not module_on('gifts'):
        raise SocialError(_('Подарки скоро появятся.'), 403)
    gift = Gift.objects.filter(pk=gift_id, active=True).first()
    if gift is None:
        raise SocialError(_('Подарок не найден'), 404)
    if receiver.pk == user.pk:
        raise SocialError(_('Себе подарок не отправить.'))
    if gift.price:
        raise SocialError(_('Платные подарки появятся вместе с оплатой из кошелька.'), 403)
    return UserGift.objects.create(gift=gift, sender=user, receiver=receiver, message=(message or '').strip()[:200],
                                   anonymous=bool(anonymous))


def gifts_of(person, viewer=None) -> list:
    qs = UserGift.objects.filter(receiver=person, on_profile=True).select_related('gift', 'sender')
    return [{'id': g.pk, 'title': g.gift.title, 'emoji': g.gift.emoji, 'image': g.gift.image.url if g.gift.image else '',
             'message': g.message, 'from': None if g.anonymous or g.sender is None else _person(g.sender),
             'created': g.created_at} for g in qs[:60]]
