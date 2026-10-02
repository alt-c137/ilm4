"""Люди «как в Telegram»: @имя, поиск по имени и номеру, приватность номера / времени в сети / соцсетей,
близкие друзья, начало диалога, «без звука», вложения чата."""
import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts import people
from apps.accounts.models import CloseFriend, UserBlock
from apps.api.models import ApiToken
from apps.chat import rooms, services
from apps.core.models import ModuleConfig

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def trio(db, settings):
    settings.PUSH_DISABLED = True
    ModuleConfig.objects.update_or_create(key='chat', defaults={'name': 'Чат', 'status': 'on'})
    return [User.objects.create_user(n, f'{n}@x.com', 'x', nickname=n.title()) for n in ('ali', 'umar', 'zayd')]


def call(client, method, url, user, data=None):
    headers = {'HTTP_AUTHORIZATION': f'Bearer {ApiToken.issue(user, "test")}'}
    if method == 'get':
        return client.get(url, data or {}, **headers)
    return client.post(url, json.dumps(data or {}), content_type='application/json', **headers)


def test_handle_rules(trio):
    ali, umar, _z = trio
    assert people.clean_handle('@Ali_2024', user=ali) == 'ali_2024'
    assert people.clean_handle('abc4', user=ali) == 'abc4'                      # буквы и цифра, 4 знака — можно
    for bad in ('ab', '4ali', 'али', 'a b c d', 'x' * 40):
        with pytest.raises(people.PeopleError):
            people.clean_handle(bad, user=ali)
    with pytest.raises(people.PeopleError):                                    # «ilm4» — только сотрудникам
        people.clean_handle('ilm4', user=ali)
    ali.is_staff = True
    assert people.clean_handle('ilm4', user=ali) == 'ilm4'
    umar.handle = 'umar_x'
    umar.save()
    with pytest.raises(people.PeopleError):
        people.clean_handle('umar_x', user=ali)
    assert people.clean_handle('umar_x', user=umar) == 'umar_x'               # своё имя сохранять можно
    # группа не может занять имя человека, человек — имя группы
    with pytest.raises(services.ChatError):
        rooms.clean_handle('umar_x', user=ali)
    g = rooms.create(ali, 'channel', 'Официальный', is_public=True, handle='ilm4')
    assert g.handle == 'ilm4'
    with pytest.raises(people.PeopleError):
        people.clean_handle('ilm4', user=ali)


def test_search_by_handle_and_phone(trio, client):
    ali, umar, zayd = trio
    umar.handle = 'umar_farukh'
    umar.phone, umar.phone_verified_at = '+998 90 123 45 67', timezone.now()
    umar.save()
    zayd.phone = '+998 90 765 43 21'                                           # номер не подтверждён
    zayd.save()
    r = call(client, 'get', '/api/v1/people/', ali, {'q': '@umar'}).json()
    assert [x['id'] for x in r['items']] == [umar.pk] and r['items'][0]['handle'] == 'umar_farukh'
    assert call(client, 'get', '/api/v1/people/', ali, {'q': 'Umar'}).json()['items'][0]['id'] == umar.pk
    # по номеру — в любом написании; сам номер в ответе не отдаётся
    r = call(client, 'get', '/api/v1/people/', ali, {'q': '8 (90) 123-45-67'}).json()
    assert [x['id'] for x in r['items']] == [umar.pk] and 'phone' not in r['items'][0]
    # неподтверждённый номер не находится; запретивший поиск — тоже
    assert call(client, 'get', '/api/v1/people/', ali, {'q': '+998907654321'}).json()['items'] == []
    umar.findable_by_phone = False
    umar.save()
    r = call(client, 'get', '/api/v1/people/', ali, {'q': '+998901234567'}).json()
    assert r['items'] == [] and r['hint']
    # заблокированный не находится
    UserBlock.objects.create(blocker=umar, blocked=ali)
    assert call(client, 'get', '/api/v1/people/', ali, {'q': 'umar_farukh'}).json()['items'] == []


def test_phone_search_is_rate_limited(trio, client):
    ali = trio[0]
    for _i in range(30):
        assert call(client, 'get', '/api/v1/people/', ali, {'q': '+998900000000'}).status_code == 200
    assert call(client, 'get', '/api/v1/people/', ali, {'q': '+998900000000'}).status_code == 429


def test_start_chat_contacts_and_mute(trio, client):
    ali, umar, _z = trio
    r = call(client, 'post', f'/api/v1/users/{umar.pk}/chat/', ali)
    assert r.status_code == 200
    tid = r.json()['thread']
    assert call(client, 'post', f'/api/v1/users/{umar.pk}/chat/', ali).json()['thread'] == tid      # тот же диалог
    assert call(client, 'post', f'/api/v1/users/{ali.pk}/chat/', ali).status_code == 400
    # теперь Умар — «контакт»: находится по имени без @имени
    r = call(client, 'get', '/api/v1/people/', ali).json()
    assert [x['id'] for x in r['contacts']] == [umar.pk]
    assert [x['id'] for x in call(client, 'get', '/api/v1/people/', ali, {'q': 'uma'}).json()['contacts']] == [umar.pk]
    # «без звука» в личном диалоге: уведомление собеседнику приходит тихим
    from apps.core.models import Notification
    assert call(client, 'post', f'/api/v1/chat/{tid}/mute/', umar, {'on': True}).json() == {'muted': True}
    services.send_text(services.direct_between(ali, umar), ali, 'Салам')
    assert Notification.objects.get(user=umar).silent is True
    prof = call(client, 'get', f'/api/v1/users/{ali.pk}/', umar).json()
    assert prof['thread'] == tid and prof['muted'] is True
    assert call(client, 'post', f'/api/v1/chat/{tid}/mute/', umar, {'on': False}).json() == {'muted': False}
    # заблокированному написать нельзя
    UserBlock.objects.create(blocker=umar, blocked=trio[2])
    assert call(client, 'post', f'/api/v1/users/{umar.pk}/chat/', trio[2]).status_code == 403


def test_profile_privacy_phone_links_close_friends(trio, client):
    ali, umar, zayd = trio
    ali.phone, ali.bio = '+998901112233', 'Учу Коран'
    ali.save()
    r = call(client, 'post', '/api/v1/me/links/', ali, {'links': [
        {'kind': 'instagram', 'value': '@ali.insta', 'privacy': 'all'},
        {'kind': 'telegram', 'value': 'https://t.me/ali_tg', 'privacy': 'close'},
        {'kind': 'github', 'value': 'ali-dev', 'privacy': 'nobody'},
        {'kind': 'discord', 'value': 'ali#1234', 'privacy': 'all'}]})
    assert r.status_code == 200 and len(r.json()['links']) == 4
    # чужой: номер скрыт (по умолчанию «никто»), видит только ссылки «для всех»
    p = call(client, 'get', f'/api/v1/users/{ali.pk}/', umar).json()
    assert p['phone'] == '' and p['bio'] == 'Учу Коран'
    assert [(x['kind'], x['url']) for x in p['links']] == [('instagram', 'https://instagram.com/ali.insta'), ('discord', '')]
    assert 'privacy' not in p['links'][0]
    # Али добавил Умара в близкие и открыл номер близким
    assert call(client, 'post', f'/api/v1/users/{umar.pk}/close/', ali, {'on': True}).json() == {'close': True}
    assert call(client, 'post', '/api/v1/me/', ali, {'phone_privacy': 'close'}).json()['privacy']['phone'] == 'close'
    p = call(client, 'get', f'/api/v1/users/{ali.pk}/', umar).json()
    assert p['phone'] == '+998901112233' and [x['kind'] for x in p['links']] == ['instagram', 'telegram', 'discord']
    assert p['close'] is False                                                # Умар Али в близкие не добавлял
    assert call(client, 'get', f'/api/v1/users/{ali.pk}/', zayd).json()['phone'] == ''
    assert [x['id'] for x in call(client, 'get', '/api/v1/me/close/', ali).json()['items']] == [umar.pk]
    # «все» — номер виден каждому; сам себе — всегда всё
    call(client, 'post', '/api/v1/me/', ali, {'phone_privacy': 'all'})
    assert call(client, 'get', f'/api/v1/users/{ali.pk}/', zayd).json()['phone'] == '+998901112233'
    mine = call(client, 'get', f'/api/v1/users/{ali.pk}/', ali).json()
    assert mine['me'] and len(mine['links']) == 4 and mine['links'][2]['privacy'] == 'nobody'
    assert call(client, 'post', f'/api/v1/users/{umar.pk}/close/', ali, {'on': False}).json() == {'close': False}
    assert not CloseFriend.objects.exists()


def test_bad_links_refused(trio, client):
    ali = trio[0]
    for row in ({'kind': 'instagram', 'value': 'https://evil.example/ali'}, {'kind': 'website', 'value': 'javascript:alert(1)'},
                {'kind': 'whatsapp', 'value': '12'}, {'kind': 'nope', 'value': 'x'}):
        assert call(client, 'post', '/api/v1/me/links/', ali, {'links': [row]}).status_code == 400, row
    r = call(client, 'post', '/api/v1/me/links/', ali, {'links': [{'kind': 'website', 'value': 'ali.uz'}]}).json()
    assert r['links'][0]['url'] == 'https://ali.uz'


def test_presence_online_last_seen_and_reciprocity(trio, client):
    ali, umar, zayd = trio
    # запрос к API отмечает человека «в сети»
    call(client, 'post', '/api/v1/ping/', ali)
    ali.refresh_from_db()
    assert ali.last_seen_at is not None
    pr = call(client, 'get', f'/api/v1/users/{ali.pk}/', umar).json()['presence']
    assert pr == {'online': True, 'seen': ali.last_seen_at.isoformat(), 'hidden': False}
    # давно не заходил — «был(а) в …»
    User.objects.filter(pk=ali.pk).update(last_seen_at=timezone.now() - timedelta(hours=3))
    pr = call(client, 'get', f'/api/v1/users/{ali.pk}/', umar).json()['presence']
    assert pr['online'] is False and pr['seen'] and not pr['hidden']
    # Али скрыл время — «был(а) недавно»; близкому другу (при «близкие друзья») — видно
    call(client, 'post', '/api/v1/me/', ali, {'seen_privacy': 'nobody'})
    User.objects.filter(pk=ali.pk).update(last_seen_at=timezone.now() - timedelta(hours=3))
    assert call(client, 'get', f'/api/v1/users/{ali.pk}/', umar).json()['presence'] == {'online': False, 'seen': None, 'hidden': True}
    call(client, 'post', '/api/v1/me/', ali, {'seen_privacy': 'close'})
    CloseFriend.objects.create(owner=ali, friend=umar)
    assert call(client, 'get', f'/api/v1/users/{ali.pk}/', umar).json()['presence']['hidden'] is False
    assert call(client, 'get', f'/api/v1/users/{ali.pk}/', zayd).json()['presence']['hidden'] is True
    # взаимность: Зайд скрыл своё время — чужое тоже не видит
    call(client, 'post', '/api/v1/me/', ali, {'seen_privacy': 'all'})
    call(client, 'post', '/api/v1/me/', zayd, {'seen_privacy': 'nobody'})
    assert call(client, 'get', f'/api/v1/users/{ali.pk}/', zayd).json()['presence']['hidden'] is True
    # шапка чата и список чатов
    t = services.open_direct(umar, ali)
    User.objects.filter(pk=ali.pk).update(last_seen_at=timezone.now())
    th = call(client, 'get', f'/api/v1/chat/{t.pk}/', umar).json()['thread']
    assert th['presence']['online'] is True and th['other_id'] == ali.pk
    services.send_text(t, ali, 'Салам')
    assert call(client, 'get', '/api/v1/chat/', umar).json()['items'][0]['online'] is True


def test_me_handle_bio_and_shared_media(trio, client):
    ali, umar, _z = trio
    r = call(client, 'post', '/api/v1/me/', ali, {'handle': '@Ali_Dev', 'bio': 'Привет'})
    assert r.status_code == 200 and r.json()['handle'] == 'ali_dev' and r.json()['bio'] == 'Привет'
    assert call(client, 'post', '/api/v1/me/', umar, {'handle': 'ali_dev'}).status_code == 400
    assert call(client, 'post', '/api/v1/me/', ali, {'handle': ''}).json()['handle'] == ''
    t = services.open_direct(ali, umar)
    assert call(client, 'get', f'/api/v1/chat/{t.pk}/media/', ali, {'what': 'media'}).json() == {'items': [], 'more': False}
    assert call(client, 'get', f'/api/v1/chat/{t.pk}/media/', trio[2], {'what': 'media'}).status_code == 404


# ---------- сайт ----------

def test_site_people_page_search_and_start_chat(trio, client):
    ali, umar, _z = trio
    umar.handle = 'umar_farukh'
    umar.save()
    client.force_login(ali)
    html = client.get('/chat/people/').content.decode()
    assert 'Новое сообщение' in html and 'Новая группа' in html and 'Новый канал' in html
    html = client.get('/chat/people/', {'q': '@umar'}).content.decode()
    assert 'umar_farukh' in html and f'/chat/start/?user={umar.pk}' in html
    data = client.get('/chat/people/', {'q': 'umar_f', 'json': 1}).json()
    assert [p['id'] for p in data['found']] == [umar.pk]
    r = client.get(f'/chat/start/?user={umar.pk}')
    assert r.status_code == 302
    thread = services.direct_between(ali, umar)
    assert r.url == f'/chat/{thread.pk}/'
    assert client.get(f'/chat/start/?user={umar.pk}&call=video').url == f'/chat/{thread.pk}/?call=video'
    # шапка чата ведёт в профиль и показывает «в сети»
    User.objects.filter(pk=umar.pk).update(last_seen_at=timezone.now())
    html = client.get(f'/chat/{thread.pk}/').content.decode()
    assert f'/accounts/u/{umar.pk}/' in html and 'в сети' in html
    # в списке чатов кнопка «написать» ведёт на поиск людей
    assert '/chat/people/' in client.get('/chat/').content.decode()
    # «без звука» из профиля
    assert client.post(f'/chat/{thread.pk}/mute/', {'next': f'/accounts/u/{umar.pk}/'}).url == f'/accounts/u/{umar.pk}/'
    assert services.is_muted(thread, ali)


def test_site_public_profile_respects_privacy(trio, client):
    ali, umar, zayd = trio
    ali.phone, ali.handle, ali.bio = '+998901112233', 'ali_dev', 'Учу Коран'
    ali.save()
    people.set_links(ali, [{'kind': 'instagram', 'value': 'ali.insta', 'privacy': 'all'},
                           {'kind': 'github', 'value': 'ali-secret', 'privacy': 'close'}])
    client.force_login(umar)
    html = client.get(f'/accounts/u/{ali.pk}/').content.decode()
    assert '@ali_dev' in html and 'Учу Коран' in html and 'ali.insta' in html
    assert '+998901112233' not in html and 'ali-secret' not in html
    assert 'Добавить в близкие друзья' in html
    # Али добавил Умара в близкие и открыл номер близким
    client.force_login(ali)
    assert client.post(f'/accounts/u/{umar.pk}/close/').status_code == 302
    assert people.is_close(ali, umar)
    r = client.post('/accounts/profile/', {'nickname': 'Ali', 'first_name': '', 'city': '', 'handle': 'ali_dev', 'bio': 'Учу Коран',
                                           'phone': '+998901112233', 'findable_by_phone': 'on', 'phone_privacy': 'close',
                                           'seen_privacy': 'all', 'link_kind': ['instagram', 'github'],
                                           'link_value': ['ali.insta', 'ali-secret'], 'link_privacy': ['all', 'close']})
    assert r.status_code == 302
    client.force_login(umar)
    html = client.get(f'/accounts/u/{ali.pk}/').content.decode()
    assert '+998901112233' in html and 'ali-secret' in html
    client.force_login(zayd)
    html = client.get(f'/accounts/u/{ali.pk}/').content.decode()
    assert '+998901112233' not in html and 'ali-secret' not in html
    # гость (без входа) видит только открытое
    client.logout()
    html = client.get(f'/accounts/u/{ali.pk}/').content.decode()
    assert 'ali.insta' in html and '+998901112233' not in html and 'был(а) недавно' in html


def test_site_profile_form_handle_errors_and_phone_change_resets_verification(trio, client):
    ali, umar, _z = trio
    umar.handle = 'taken_name'
    umar.save()
    ali.phone, ali.phone_verified_at = '+998901112233', timezone.now()
    ali.save()
    client.force_login(ali)
    base = {'nickname': 'Ali', 'first_name': '', 'city': '', 'bio': '', 'findable_by_phone': 'on'}
    html = client.post('/accounts/profile/', {**base, 'handle': 'taken_name', 'phone': '+998901112233'}).content.decode()
    assert 'Это имя уже занято' in html
    assert client.post('/accounts/profile/', {**base, 'handle': 'ali_ok', 'phone': '+998 90 111-22-33'}).status_code == 302
    ali.refresh_from_db()
    assert ali.handle == 'ali_ok' and ali.phone_verified_at is not None        # тот же номер, другое написание
    assert client.post('/accounts/profile/', {**base, 'handle': 'ali_ok', 'phone': '+998909999999'}).status_code == 302
    ali.refresh_from_db()
    assert ali.phone_verified_at is None                                       # номер другой — подтверждать заново
    # плохая ссылка — профиль сохранён, ошибка показана
    html = client.post('/accounts/profile/', {**base, 'handle': 'ali_ok', 'phone': '', 'link_kind': ['instagram'],
                                              'link_value': ['https://evil.example/x'], 'link_privacy': ['all']}).content.decode()
    assert 'Ссылка не похожа на Instagram' in html
