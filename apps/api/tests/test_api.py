"""API мобильного приложения: вход, выключатели разделов, публикации, никях, чат, WebSocket."""
import io
import json

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.api.models import ApiToken
from apps.core.models import Moderation, ModuleConfig, SiteSettings

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def modules(settings):
    settings.PUSH_DISABLED = True
    for key in ('buy', 'jobs', 'nikah', 'chat', 'news', 'wallet', 'forum', 'map'):
        ModuleConfig.objects.update_or_create(key=key, defaults={'name': key, 'status': 'on'})


def call(client, method, url, data=None, token=None, **extra):
    headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'} if token else {}
    fn = getattr(client, method)
    if method == 'get':
        return fn(url, data or {}, **headers, **extra)
    return fn(url, json.dumps(data or {}), content_type='application/json', **headers, **extra)


def token_for(user):
    return ApiToken.issue(user, 'test')


def jpeg(name='p.jpg'):
    buf = io.BytesIO()
    Image.new('RGB', (40, 30), (10, 120, 10)).save(buf, 'JPEG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg')


# ---------- вход ----------

def test_register_login_logout(client):
    r = call(client, 'post', '/api/v1/auth/register/', {'email': 'App@x.com', 'password': 'Strong-pass-123',
                                                        'name': 'Абдулла', 'language': 'uz'})
    assert r.status_code == 200, r.content
    tok = r.json()['token']
    assert r.json()['user']['email'] == 'app@x.com'
    assert User.objects.get(email='app@x.com').language == 'uz'
    # токен в базе — только хешем
    assert not ApiToken.objects.filter(key_hash=tok).exists()
    assert call(client, 'get', '/api/v1/me/', token=tok).json()['name'] == 'Абдулла'
    # вход паролем
    r = call(client, 'post', '/api/v1/auth/login/', {'login': 'app@x.com', 'password': 'Strong-pass-123'})
    assert r.status_code == 200 and r.json()['token'] != tok
    # выход — токен больше не работает
    assert call(client, 'post', '/api/v1/auth/logout/', token=tok).status_code == 200
    assert call(client, 'get', '/api/v1/me/', token=tok).status_code == 401


def test_login_wrong_password_and_rate_limit(client):
    User.objects.create_user('u', 'u@x.com', 'right-pass-1')
    for _i in range(8):
        assert call(client, 'post', '/api/v1/auth/login/', {'login': 'u@x.com', 'password': 'bad'}).status_code == 400
    r = call(client, 'post', '/api/v1/auth/login/', {'login': 'u@x.com', 'password': 'right-pass-1'})
    assert r.status_code == 429


def test_session_cookie_is_ignored(client):
    """API не принимает вход по сессии сайта — только токен (иначе нужен CSRF)."""
    user = User.objects.create_user('s', 's@x.com', 'x')
    client.force_login(user)
    assert call(client, 'get', '/api/v1/me/').status_code == 401


def test_blocked_user_token_rejected(client):
    user = User.objects.create_user('b', 'b@x.com', 'x')
    tok = token_for(user)
    user.is_active = False
    user.save()
    assert call(client, 'get', '/api/v1/me/', token=tok).status_code == 401


def test_telegram_login_flow(client, settings):
    """Приложение → код → бот спрашивает «это вы?» → кнопка → приложение получает токен."""
    from apps.api import tglogin
    settings.TELEGRAM_BOT_USERNAME = 'ilm4_bot'
    r = call(client, 'post', '/api/v1/auth/telegram/start/')
    nonce = r.json()['nonce']
    assert r.json()['url'] == f'https://t.me/ilm4_bot?start=login_{nonce}'
    assert call(client, 'post', '/api/v1/auth/telegram/poll/', {'nonce': nonce}).json()['status'] == 'pending'
    answer = tglogin.bot_confirm({'data': f'lg:{nonce}', 'from': {'id': 777, 'first_name': 'Иса'}})
    assert 'Готово' in answer
    r = call(client, 'post', '/api/v1/auth/telegram/poll/', {'nonce': nonce})
    assert r.json()['status'] == 'ok' and r.json()['user']['telegram']
    assert User.objects.get(telegram_id=777)
    # код одноразовый
    assert call(client, 'post', '/api/v1/auth/telegram/poll/', {'nonce': nonce}).status_code == 410


def test_delete_account(client):
    user = User.objects.create_user('d', 'd@x.com', 'x')
    tok = token_for(user)
    assert call(client, 'delete', '/api/v1/me/', {'confirm': 'нет'}, token=tok).status_code == 400
    assert call(client, 'delete', '/api/v1/me/', {'confirm': 'удалить'}, token=tok).status_code == 200
    user.refresh_from_db()
    assert not user.is_active and not ApiToken.objects.filter(user=user).exists()


# ---------- настройки и выключатели ----------

def test_config_follows_admin_switches(client):
    st = SiteSettings.get_solo()
    st.chat_video_calls_enabled = False
    st.app_min_version = '1.1.0'
    st.save()
    ModuleConfig.objects.filter(key='buy').update(status='off')
    data = call(client, 'get', '/api/v1/config/').json()
    keys = {m['key'] for m in data['modules']}
    assert 'buy' not in keys and 'nikah' in keys
    assert data['features']['chat']['video_calls'] is False
    assert data['min_version'] == '1.1.0'
    assert any(c['key'] == 'tashkent' for c in data['prayer']['cities'])
    # выключенный маркет недоступен и через API
    assert call(client, 'get', '/api/v1/pubs/buy/').status_code == 404


def test_config_translated(client):
    ModuleConfig.objects.filter(key='nikah').update(name='Никях')
    data = call(client, 'get', '/api/v1/config/', HTTP_X_LANG='en').json()
    assert any(m['name'] == 'Nikah' for m in data['modules']), [m['name'] for m in data['modules']]


# ---------- публикации ----------

def test_pubs_list_detail_and_message(client):
    from apps.market.models import Category, Listing
    seller = User.objects.create_user('sel', 'sel@x.com', 'x')
    buyer = User.objects.create_user('buy', 'buy@x.com', 'x')
    cat = Category.objects.create(name='Тест-одежда', slug='t-clothes')
    ok = Listing.objects.create(title='Коврик', description='Новый', price=50000, category=cat, city='Ташкент',
                                owner=seller, status=Moderation.APPROVED)
    Listing.objects.create(title='Скрытый', description='-', price=1, category=cat, city='Ташкент',
                           owner=seller, status=Moderation.PENDING)
    data = call(client, 'get', '/api/v1/pubs/buy/').json()
    assert [x['title'] for x in data['items']] == ['Коврик']
    assert any(c['key'] == 't-clothes' for c in data['categories'])
    # SQLite различает регистр кириллицы (в PostgreSQL — нет), поэтому ищем с заглавной
    assert call(client, 'get', '/api/v1/pubs/buy/', {'q': 'Ковр'}).json()['items']
    assert not call(client, 'get', '/api/v1/pubs/buy/', {'q': 'телефон'}).json()['items']
    d = call(client, 'get', f'/api/v1/pubs/buy/{ok.pk}/').json()
    assert d['owner']['id'] == seller.pk and any(f['value'].startswith('50 000') for f in d['fields'])
    tok = token_for(buyer)
    r = call(client, 'post', f'/api/v1/pubs/buy/{ok.pk}/message/', token=tok)
    assert r.status_code == 200
    from apps.chat.models import Thread
    t = Thread.objects.get(pk=r.json()['thread_id'])
    assert set(t.participants.all()) == {seller, buyer}
    # тот же диалог при повторе
    assert call(client, 'post', f'/api/v1/pubs/buy/{ok.pk}/message/', token=tok).json()['thread_id'] == t.pk


def test_report_hides_after_three(client):
    from apps.market.models import Category, Listing
    owner = User.objects.create_user('o', 'o@x.com', 'x')
    cat = Category.objects.create(name='Тест-разное', slug='t-other')
    lst = Listing.objects.create(title='Спам', description='-', price=1, category=cat, city='Т',
                                 owner=owner, status=Moderation.APPROVED)
    for i in range(3):
        u = User.objects.create_user(f'r{i}', f'r{i}@x.com', 'x')
        r = call(client, 'post', '/api/v1/report/', {'type': 'buy', 'id': lst.pk, 'reason': 'spam'}, token=token_for(u))
        assert r.status_code == 200
    lst.refresh_from_db()
    assert lst.status == Moderation.PENDING
    assert call(client, 'post', '/api/v1/report/', {'type': 'buy', 'id': lst.pk, 'reason': 'spam'},
                token=token_for(owner)).status_code == 400


# ---------- никях ----------

def _wizard(gender):
    from apps.nikah.tests.test_nikah import wizard_data
    return wizard_data(gender, relocation='stay')


def test_nikah_profile_via_api_then_match(client):
    from apps.nikah.models import NikahMatch, NikahProfile
    bro, sis = User.objects.create_user('nb', 'nb@x.com', 'x'), User.objects.create_user('ns', 'ns@x.com', 'x')
    tb, ts = token_for(bro), token_for(sis)
    assert call(client, 'get', '/api/v1/nikah/feed/', token=tb).json()['code'] == 'no_profile'
    # без обязательств — ошибка по полю
    bad = _wizard('M')
    bad.pop('agree_rules')
    r = call(client, 'post', '/api/v1/nikah/profile/', bad, token=tb)
    assert r.status_code == 400 and 'pledges' in r.json()['fields']
    assert call(client, 'post', '/api/v1/nikah/profile/', _wizard('M'), token=tb).status_code == 200
    assert call(client, 'post', '/api/v1/nikah/profile/', _wizard('F'), token=ts).status_code == 200
    assert NikahProfile.objects.filter(status=Moderation.PENDING).count() == 2
    # до одобрения — интерес нельзя, в ленте никого
    assert call(client, 'get', '/api/v1/nikah/feed/', token=tb).json()['items'] == []
    NikahProfile.objects.update(status=Moderation.APPROVED)
    feed = call(client, 'get', '/api/v1/nikah/feed/', token=tb).json()
    assert len(feed['items']) == 1 and 'compat' in feed['items'][0]
    sid = feed['items'][0]['id']
    assert call(client, 'post', f'/api/v1/nikah/p/{sid}/interest/', {'from_deck': 1}, token=tb).json()['match_id'] is None
    bid = NikahProfile.objects.get(user=bro).pk
    mid = call(client, 'post', f'/api/v1/nikah/p/{bid}/interest/', token=ts).json()['match_id']
    assert mid and NikahMatch.objects.filter(pk=mid).exists()
    lists = call(client, 'get', '/api/v1/nikah/lists/', token=tb).json()
    assert lists['matches'][0]['id'] == mid
    m = call(client, 'get', f'/api/v1/nikah/match/{mid}/', token=ts).json()
    assert m['side'] == 'sister'
    # чужая пара — не видна
    other = User.objects.create_user('x3', 'x3@x.com', 'x')
    call(client, 'post', '/api/v1/nikah/profile/', _wizard('M'), token=token_for(other))
    assert call(client, 'get', f'/api/v1/nikah/match/{mid}/', token=ApiToken.issue(other)).status_code == 404


def test_nikah_same_gender_hidden(client):
    from apps.nikah.tests.test_nikah import make_profile
    a, b = make_profile('a@x.com', 'M'), make_profile('b@x.com', 'M')
    assert call(client, 'get', f'/api/v1/nikah/p/{b.pk}/', token=token_for(a.user)).status_code == 404


def test_nikah_options_by_gender(client):
    from apps.nikah.tests.test_nikah import make_profile
    p = make_profile('o@x.com', 'F')
    data = call(client, 'get', '/api/v1/nikah/options/', {'gender': 'F'}, token=token_for(p.user)).json()
    assert {x['key'] for x in data['marital']} == {'never', 'divorced', 'widowed'}   # «женат» — только брату
    assert data['look'][0]['key'] == 'niqab' and len(data['pledges']) == 5


# ---------- чат ----------

@pytest.fixture
def pair():
    from apps.chat.models import Thread
    a = User.objects.create_user('ca', 'ca@x.com', 'x')
    b = User.objects.create_user('cb', 'cb@x.com', 'x')
    t = Thread.objects.create()
    t.participants.add(a, b)
    return a, b, t


def test_chat_send_list_read(client, pair):
    a, b, t = pair
    ta, tb = token_for(a), token_for(b)
    r = call(client, 'post', f'/api/v1/chat/{t.pk}/send/', {'body': 'Ассаляму алейкум'}, token=ta)
    assert r.status_code == 200 and r.json()['mine']
    threads = call(client, 'get', '/api/v1/chat/', token=tb).json()['items']
    assert threads[0]['unread'] == 1 and threads[0]['preview'] == 'Ассаляму алейкум'
    msgs = call(client, 'get', f'/api/v1/chat/{t.pk}/', token=tb).json()
    assert msgs['items'][0]['body'] == 'Ассаляму алейкум' and not msgs['items'][0]['mine']
    assert call(client, 'get', '/api/v1/chat/', token=tb).json()['items'][0]['unread'] == 0
    # постороннему — нет
    c = User.objects.create_user('cc', 'cc@x.com', 'x')
    assert call(client, 'get', f'/api/v1/chat/{t.pk}/', token=token_for(c)).status_code == 404
    assert call(client, 'post', f'/api/v1/chat/{t.pk}/send/', {'body': 'x'}, token=token_for(c)).status_code == 404


def test_chat_upload_and_file_by_token(client, pair, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    a, b, t = pair
    r = client.post(f'/api/v1/chat/{t.pk}/upload/', {'kind': 'photo', 'file': jpeg()},
                    HTTP_AUTHORIZATION=f'Bearer {token_for(a)}')
    assert r.status_code == 200, r.content
    url = r.json()['url']
    assert url.endswith(f'/api/v1/chat/file/{r.json()["id"]}/')
    assert client.get(url, HTTP_AUTHORIZATION=f'Bearer {token_for(b)}').status_code == 200
    c = User.objects.create_user('cx', 'cx@x.com', 'x')
    assert client.get(url, HTTP_AUTHORIZATION=f'Bearer {token_for(c)}').status_code == 404
    assert client.get(url).status_code == 401


def test_chat_disabled_feature_via_api(client, pair, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    st = SiteSettings.get_solo()
    st.chat_photos_enabled = False
    st.save()
    a, _b, t = pair
    r = client.post(f'/api/v1/chat/{t.pk}/upload/', {'kind': 'photo', 'file': jpeg()},
                    HTTP_AUTHORIZATION=f'Bearer {token_for(a)}')
    assert r.status_code == 403
    assert call(client, 'get', f'/api/v1/chat/{t.pk}/', token=token_for(a)).json()['thread']['features']['photo'] is False


def test_push_register_and_notification(client, pair, monkeypatch, django_capture_on_commit_callbacks):
    """Новое уведомление (колокольчик) уходит пушем на телефон получателя."""
    from apps.api import push
    from apps.api.models import PushDevice
    a, b, t = pair
    assert call(client, 'post', '/api/v1/push/', {'token': 'ExponentPushToken[abc]', 'platform': 'android'},
                token=token_for(b)).status_code == 200
    assert PushDevice.objects.filter(user=b).count() == 1
    assert call(client, 'post', '/api/v1/push/', {'token': 'evil'}, token=token_for(b)).status_code == 400
    sent = []
    monkeypatch.setattr(push, 'send_to_user', lambda uid, body, url='', title='ilm4': sent.append((uid, body, url)))
    with django_capture_on_commit_callbacks(execute=True):
        call(client, 'post', f'/api/v1/chat/{t.pk}/send/', {'body': 'Салам'}, token=token_for(a))
    assert sent and sent[0][0] == b.pk and 'Салам' in sent[0][1] and sent[0][2] == f'/chat/{t.pk}/'


# ---------- WebSocket приложения ----------

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_ws_token_auth():
    from channels.db import database_sync_to_async
    from channels.testing import WebsocketCommunicator

    from config.asgi import application

    def setup():
        from apps.chat.models import Thread
        a = User.objects.create_user('wa', 'wa@x.com', 'x')
        b = User.objects.create_user('wb', 'wb@x.com', 'x')
        t = Thread.objects.create()
        t.participants.add(a, b)
        ModuleConfig.objects.update_or_create(key='chat', defaults={'name': 'chat', 'status': 'on'})
        return t.pk, ApiToken.issue(a), ApiToken.issue(User.objects.create_user('wc', 'wc@x.com', 'x'))
    tid, tok, stranger = await database_sync_to_async(setup)()
    # без Origin (как в приложении), с токеном — пускает
    comm = WebsocketCommunicator(application, f'/ws/chat/{tid}/', headers=[(b'authorization', f'Bearer {tok}'.encode())])
    connected, _ = await comm.connect()
    assert connected
    await comm.send_json_to({'body': 'из приложения'})
    msg = await comm.receive_json_from()
    assert msg['type'] == 'msg' and msg['body'] == 'из приложения'
    await comm.disconnect()
    # чужой токен — не участник
    comm = WebsocketCommunicator(application, f'/ws/chat/{tid}/', headers=[(b'authorization', f'Bearer {stranger}'.encode())])
    connected, _ = await comm.connect()
    assert not connected
    # без токена и без Origin — отказ (путь сайта требует Origin)
    comm = WebsocketCommunicator(application, f'/ws/chat/{tid}/')
    connected, _ = await comm.connect()
    assert not connected


def test_web_link_one_time(client):
    user = User.objects.create_user('wl', 'wl@x.com', 'x')
    url = call(client, 'post', '/api/v1/auth/web-link/', {'next': '/wallet/topup/'}, token=token_for(user)).json()['url']
    path = url.split('testserver')[-1]
    r = client.get(path)
    assert r.status_code == 302 and r['Location'] == '/wallet/topup/'
    assert int(client.session['_auth_user_id']) == user.pk
    client.logout()
    assert client.get(path)['Location'] == '/accounts/login/'          # второй раз не работает
    # чужой сайт в next не подставить
    url = call(client, 'post', '/api/v1/auth/web-link/', {'next': 'https://evil.com/'}, token=token_for(user)).json()['url']
    assert client.get(url.split('testserver')[-1])['Location'] == '/'


# ---------- подача публикаций из приложения ----------

def test_pub_form_schema_and_create(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    from apps.market.models import Category, Listing
    Category.objects.get_or_create(slug='t-cat', defaults={'name': 'Тест'})
    user = User.objects.create_user('pa', 'pa@x.com', 'x')
    tok = token_for(user)
    sch = call(client, 'get', '/api/v1/pubs/buy/form/', token=tok).json()
    names = {f['name']: f for f in sch['fields']}
    assert names['description']['kind'] == 'text' and names['photo']['kind'] == 'image'
    assert any(ch['key'] for ch in names['category']['choices']) and sch['pledge']
    cat = Category.objects.get(slug='t-cat')
    data = {'title': 'Коврик', 'description': 'Новый', 'price': '100', 'currency': 'UZS', 'category': str(cat.pk),
            'city': 'Ташкент'}
    # без договора автора — нельзя
    r = client.post('/api/v1/pubs/buy/save/', data, HTTP_AUTHORIZATION=f'Bearer {tok}')
    assert r.status_code == 400 and r.json()['code'] == 'pledge'
    r = client.post('/api/v1/pubs/buy/save/', {**data, 'pledge': '1', 'photo': jpeg()}, HTTP_AUTHORIZATION=f'Bearer {tok}')
    assert r.status_code == 200, r.content
    lst = Listing.objects.get(pk=r.json()['id'])
    assert lst.owner == user and lst.photo
    # ошибки — по полям
    r = client.post('/api/v1/pubs/buy/save/', {'pledge': '1'}, HTTP_AUTHORIZATION=f'Bearer {tok}')
    assert r.status_code == 400 and 'title' in r.json()['fields']
    # правка своей → снова на проверку
    lst.status = Moderation.APPROVED
    lst.save()
    r = client.post('/api/v1/pubs/buy/save/', {**data, 'id': lst.pk, 'title': 'Коврик новый'}, HTTP_AUTHORIZATION=f'Bearer {tok}')
    assert r.status_code == 200
    lst.refresh_from_db()
    assert lst.title == 'Коврик новый' and lst.status == Moderation.PENDING
    # чужую — нельзя
    other = token_for(User.objects.create_user('pb', 'pb@x.com', 'x'))
    r = client.post('/api/v1/pubs/buy/save/', {**data, 'id': lst.pk}, HTTP_AUTHORIZATION=f'Bearer {other}')
    assert r.status_code == 404
    assert call(client, 'get', f'/api/v1/pubs/buy/form/?id={lst.pk}', token=other).status_code == 404


def test_my_publications_hide_delete(client):
    from apps.jobs.models import Vacancy
    from apps.market.models import Category, Listing
    user = User.objects.create_user('pm', 'pm@x.com', 'x')
    tok = token_for(user)
    cat = Category.objects.create(name='Т2', slug='t2')
    lst = Listing.objects.create(title='A', description='-', price=1, category=cat, city='T', owner=user,
                                 status=Moderation.APPROVED)
    Vacancy.objects.create(title='Повар', category=Vacancy._meta.get_field('category').choices[0][0], city='T',
                           description='-', contact='-', owner=user)
    data = call(client, 'get', '/api/v1/my/', token=tok).json()
    keys = {g['key'] for g in data['groups']}
    assert {'buy', 'jobs'} <= keys and any(c['key'] == 'buy' and c['native'] for c in data['create'])
    assert call(client, 'post', f'/api/v1/my/buy/{lst.pk}/', token=tok).json()['hidden'] is True
    lst.refresh_from_db()
    assert not lst.is_active
    assert call(client, 'delete', f'/api/v1/my/buy/{lst.pk}/', token=tok).status_code == 200
    assert not Listing.objects.filter(pk=lst.pk).exists()
    # чужое не удалить
    v = Vacancy.objects.get(owner=user)
    assert call(client, 'delete', f'/api/v1/my/jobs/{v.pk}/', token=token_for(User.objects.create_user('pz', 'pz@x.com', 'x'))).status_code == 404
