"""Лента как во ВКонтакте: записи, приватность, подписки, лайки, комментарии, репосты; сторис; основа шортсов и подарков."""
import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.models import CloseFriend, UserBlock
from apps.core.models import ModuleConfig
from apps.social import services
from apps.social.models import Post
from apps.social.services import SocialError

User = get_user_model()
pytestmark = pytest.mark.django_db


def jpeg(name='p.jpg'):
    buf = io.BytesIO()
    Image.new('RGB', (40, 30), (10, 120, 10)).save(buf, 'JPEG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg')


@pytest.fixture
def people(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    for key in ('feed', 'stories', 'chat'):
        ModuleConfig.objects.update_or_create(key=key, defaults={'name': key, 'status': 'on'})
    a = User.objects.create_user('a', 'a@x.com', 'x', first_name='Али')
    b = User.objects.create_user('b', 'b@x.com', 'x', first_name='Биляль')
    c = User.objects.create_user('c', 'c@x.com', 'x', first_name='Салих')
    return a, b, c


def keys(user, tab='for_you'):
    return [x['key'] for x in services.feed(user, tab)['items']]


def test_post_privacy_and_feed_tabs(people):
    a, b, c = people
    open_post = services.create_post(a, 'Ассаляму алейкум всем!', [jpeg()])
    close_post = services.create_post(a, 'Только для близких', privacy='close')
    assert open_post.photos.count() == 1
    assert f'post:{open_post.pk}' in keys(b) and f'post:{close_post.pk}' not in keys(b)
    CloseFriend.objects.create(owner=a, friend=b)
    assert f'post:{close_post.pk}' in keys(b) and f'post:{close_post.pk}' not in keys(c)
    # «Подписки» — только те, на кого подписан
    assert keys(c, 'following') == []
    services.follow(c, a)
    assert keys(c, 'following') == [f'post:{open_post.pk}']
    services.follow(c, a, False)
    assert keys(c, 'following') == []
    with pytest.raises(SocialError):
        services.follow(a, a)
    # заблокированный не видит
    UserBlock.objects.create(blocker=a, blocked=c)
    assert f'post:{open_post.pk}' not in keys(c)
    with pytest.raises(SocialError):
        services.create_post(a, '   ')


def test_likes_comments_reposts(people):
    a, b, c = people
    p = services.create_post(a, 'Пост')
    assert services.like(b, p.key) == {'liked': True, 'likes': 1}
    assert services.like(c, p.key)['likes'] == 2
    assert services.like(b, p.key) == {'liked': False, 'likes': 1}
    with pytest.raises(SocialError):
        services.like(b, 'post:99999')
    with pytest.raises(SocialError):
        services.like(b, 'evil:1')
    first = services.add_comment(b, p.key, 'МашаАллах')
    services.add_comment(c, p.key, 'Согласен', reply_to=first.pk)
    assert [x.text for x in services.comments_for(a, p.key)] == ['МашаАллах', 'Согласен']
    assert a.notifications.count() == 2 and b.notifications.count() == 1          # автору и тому, кому ответили
    with pytest.raises(SocialError):
        services.delete_comment(c, first.pk)                                   # чужой комментарий
    services.delete_comment(a, first.pk)                                       # автор записи может чистить
    item = next(x for x in services.feed(b)['items'] if x['key'] == p.key)
    assert item['likes'] == 1 and item['comments'] == 1 and not item['liked']
    # репост
    rp = services.create_post(c, '', repost_of=p.pk)
    again = services.create_post(b, 'и я', repost_of=rp.pk)
    assert rp.repost_of_id == p.pk and again.repost_of_id == p.pk                # репост репоста — на оригинал
    assert Post.objects.get(pk=p.pk).reposts == 2
    feed_item = next(x for x in services.feed(a)['items'] if x['key'] == rp.key)
    assert feed_item['repost']['id'] == p.pk
    services.delete_post(c, rp.pk)
    assert Post.objects.get(pk=p.pk).reposts == 1
    with pytest.raises(SocialError):
        services.delete_post(b, p.pk)


def test_feed_mixes_channels_and_publications(people):
    a, b, _c = people
    from apps.chat import rooms
    from apps.chat import services as chat
    from apps.core.models import SiteSettings
    from apps.news.models import NewsPost
    st = SiteSettings.get_solo()
    st.chat_channels_enabled = True
    st.phone_for_publish = False
    st.save()
    ModuleConfig.objects.update_or_create(key='news', defaults={'name': 'news', 'status': 'on'})
    news = NewsPost.objects.create(title='Рамадан начнётся', slug='ramadan', body='…')
    ch = rooms.create(a, 'channel', 'Канал мечети')
    msg = chat.send_text(ch, a, 'Джума в 13:00')
    rooms.join(ch, b, ch.invite_code)
    k = keys(b)
    assert f'msg:{msg["id"]}' in k and f'news:{news.pk}' in k
    assert services.like(b, f'msg:{msg["id"]}')['liked']
    assert services.like(b, f'news:{news.pk}')['liked']
    assert f'msg:{msg["id"]}' in keys(b, 'following') and f'news:{news.pk}' not in keys(b, 'following')
    outsider = User.objects.create_user('o', 'o@x.com', 'x')
    with pytest.raises(SocialError):
        services.like(outsider, f'msg:{msg["id"]}')                            # закрытый канал — не виден


def test_feed_paging(people):
    a, b, _c = people
    for i in range(25):
        services.create_post(a, f'Запись {i}')
    services.POSTS_PER_DAY = 100
    page1 = services.feed(b, limit=10)
    page2 = services.feed(b, before=page1['next'], limit=10)
    k1, k2 = {x['key'] for x in page1['items']}, {x['key'] for x in page2['items']}
    assert len(k1) == 10 and len(k2) == 10 and not (k1 & k2)


def test_stories(people):
    a, b, c = people
    s = services.add_story(a, jpeg(), 'Утро')
    services.follow(b, a)
    rows = services.stories_for(b)
    assert rows[0]['author']['id'] == a.pk and not rows[0]['seen']
    services.view_story(b, s.pk, '❤️')
    assert services.stories_for(b)[0]['seen']
    assert [v['reaction'] for v in services.story_viewers(a, s.pk)] == ['❤️']
    with pytest.raises(SocialError):
        services.story_viewers(b, s.pk)                                        # кто смотрел — видит только автор
    assert services.stories_for(c) == []                                       # не подписан и не общался
    ModuleConfig.objects.filter(key='stories').update(status='soon')
    with pytest.raises(SocialError):
        services.add_story(a, jpeg())


def test_shorts_and_gifts_are_switched_off_by_default(people):
    a, b, _c = people
    with pytest.raises(SocialError):
        services.add_short(a, SimpleUploadedFile('v.mp4', b'\x00\x00\x00\x18ftypmp42' + b'0' * 100))
    with pytest.raises(SocialError):
        services.send_gift(a, b, 1)
    ModuleConfig.objects.update_or_create(key='gifts', defaults={'name': 'gifts', 'status': 'on'})
    from apps.social.models import Gift
    g = Gift.objects.create(title='Роза', emoji='🌹')
    services.send_gift(a, b, g.pk, 'Джазакаллаху хайран')
    assert services.gifts_of(b)[0]['title'] == 'Роза'


def test_site_pages(people, client):
    a, b, _c = people
    p = services.create_post(a, 'Видно на сайте')
    client.force_login(b)
    page = client.get('/feed/').content.decode()
    assert 'Видно на сайте' in page and 'Что у вас нового?' in page
    r = client.post('/feed/like/', {'target': p.key}, HTTP_X_REQUESTED_WITH='fetch')
    assert r.json() == {'liked': True, 'likes': 1}
    r = client.post('/feed/comment/', {'target': p.key, 'text': 'Хорошо'}, HTTP_X_REQUESTED_WITH='fetch')
    assert r.json()['count'] == 1 and 'Хорошо' in r.json()['html']
    assert client.get(f'/feed/post/{p.pk}/').status_code == 200
    more = client.get('/feed/?more=1').json()
    assert 'Видно на сайте' in more['html']
    r = client.post('/feed/new/', {'text': 'Моя запись', 'privacy': 'all'}, HTTP_X_REQUESTED_WITH='fetch')
    assert r.json() == {'ok': True} and Post.objects.filter(author=b, text='Моя запись').exists()


def test_api(people, client):
    from apps.api.models import ApiToken
    a, b, _c = people
    ta, tb = ApiToken.issue(a, 't'), ApiToken.issue(b, 't')
    h = lambda tok: {'HTTP_AUTHORIZATION': f'Bearer {tok}'}
    r = client.post('/api/v1/feed/new/', {'text': 'Из приложения', 'photos': [jpeg()]}, **h(ta)).json()
    assert r['text'] == 'Из приложения' and r['images'][0]['url'].startswith('http')
    feed = client.get('/api/v1/feed/', **h(tb)).json()
    assert feed['items'][0]['key'] == r['key'] and feed['stories']
    import json
    js = lambda d: {'data': json.dumps(d), 'content_type': 'application/json'}
    assert client.post('/api/v1/feed/like/', **js({'target': r['key']}), **h(tb)).json() == {'liked': True, 'likes': 1}
    c = client.post('/api/v1/feed/comments/', **js({'target': r['key'], 'text': 'Отлично'}), **h(tb)).json()
    assert c['items'][0]['text'] == 'Отлично' and c['items'][0]['mine']
    f = client.post(f'/api/v1/users/{a.pk}/follow/', **js({'on': True}), **h(tb)).json()
    assert f['following'] and f['followers'] == 1
    w = client.get(f'/api/v1/feed/wall/{a.pk}/', **h(tb)).json()
    assert w['following'] and [x['key'] for x in w['items']] == [r['key']]
    s = client.post('/api/v1/feed/stories/new/', {'photo': jpeg(), 'caption': 'Утро'}, **h(ta)).json()
    st = client.get('/api/v1/feed/stories/', **h(tb)).json()
    assert st['items'][0]['items'][0]['id'] == s['id']
    assert client.post(f'/api/v1/feed/post/{r["id"]}/delete/', **h(tb)).status_code == 404
    assert client.post(f'/api/v1/feed/post/{r["id"]}/delete/', **h(ta)).json() == {'ok': True}


def test_counters_can_be_hidden(client):
    """Приватность: «Кто видит мои счётчики» — никто: чужим числа не отдаём, себе — всегда."""
    a = User.objects.create_user('ca', 'ca@x.com', 'x', first_name='Али')
    b = User.objects.create_user('cb', 'cb@x.com', 'x', first_name='Умар')
    services.follow(b, a, True)
    assert services.counts(a, b)['followers'] == 1
    a.counts_privacy = 'nobody'
    a.save(update_fields=['counts_privacy'])
    assert services.counts(a, b) == {'counts_hidden': True}
    assert services.counts(a, a)['followers'] == 1
    client.force_login(b)
    assert 'tp__counts' not in client.get(f'/accounts/u/{a.pk}/').content.decode()
