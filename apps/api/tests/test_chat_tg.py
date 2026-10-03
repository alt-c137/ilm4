"""API приложения: свои папки, состояние чата, ответ, правка, реакции, закреп, пересылка, поиск, «Избранное»,
комментарии, фото профиля — те же правила, что на сайте (apps/chat/tests/test_telegram_core.py)."""
import pytest
from django.contrib.auth import get_user_model

from apps.chat import rooms, services
from apps.chat.models import Thread
from apps.core.models import ModuleConfig, SiteSettings

from .test_api import call, jpeg, token_for

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def two(settings, tmp_path):
    settings.PUSH_DISABLED = True
    settings.MEDIA_ROOT = str(tmp_path)
    ModuleConfig.objects.update_or_create(key='chat', defaults={'name': 'chat', 'status': 'on'})
    st = SiteSettings.get_solo()
    st.chat_groups_enabled = st.chat_channels_enabled = True
    st.phone_for_publish = False
    st.save()
    a = User.objects.create_user('a', 'a@x.com', 'x', first_name='Али')
    b = User.objects.create_user('b', 'b@x.com', 'x', first_name='Биляль')
    return a, b, token_for(a), token_for(b), services.open_direct(a, b)


def test_folders_and_tabs(client, two):
    a, b, ta, _tb, t = two
    group = rooms.create(a, Thread.GROUP, 'Группа')
    services.send_text(t, b, 'салам')
    r = call(client, 'get', '/api/v1/chat/folders/', token=ta).json()
    assert r['items'] == [] and len(r['recommended']) == 4 and {x['key'] for x in r['types']} >= {'personal', 'groups'}
    r = call(client, 'post', '/api/v1/chat/folders/', {'title': 'Семья', 'emoji': '🏠', 'types': ['personal']}, token=ta).json()
    fid = r['items'][0]['id']
    call(client, 'post', '/api/v1/chat/folders/', {'recommended': 'rooms'}, token=ta)
    data = call(client, 'get', '/api/v1/chat/', token=ta).json()
    tabs = {f['title']: f for f in data['tabs']['folders']}
    assert tabs['Семья']['ids'] == [t.pk] and tabs['Семья']['unread'] == 1 and tabs['Сообщества']['ids'] == [group.pk]
    assert set(data['tabs']['all']['ids']) == {t.pk, group.pk}
    # изменить, порядок, удалить
    r = call(client, 'post', f'/api/v1/chat/folders/{fid}/', {'title': 'Близкие', 'include': [group.pk]}, token=ta).json()
    assert r['title'] == 'Близкие' and r['include'] == [group.pk]
    ids = [f['id'] for f in call(client, 'get', '/api/v1/chat/folders/', token=ta).json()['items']]
    r = call(client, 'post', '/api/v1/chat/folders/', {'order': ids[::-1]}, token=ta).json()
    assert [f['id'] for f in r['items']] == ids[::-1]
    assert call(client, 'delete', f'/api/v1/chat/folders/{fid}/', token=ta).status_code == 200
    assert call(client, 'get', f'/api/v1/chat/folders/{fid}/', token=ta).status_code == 404
    # чужая папка недоступна
    other = call(client, 'get', '/api/v1/chat/folders/', token=ta).json()['items'][0]['id']
    assert call(client, 'post', f'/api/v1/chat/folders/{other}/', {'title': 'взлом'}, token=two[3]).status_code == 404


def test_chat_state(client, two):
    _a, b, ta, tb, t = two
    services.send_text(t, b, 'раз')
    for action in ('pin', 'archive', 'unread', 'mute'):
        assert call(client, 'post', f'/api/v1/chat/{t.pk}/state/{action}/', token=ta).status_code == 200
    item = call(client, 'get', '/api/v1/chat/', token=ta).json()
    row = item['items'][0]
    assert row['archived'] and row['muted'] and row['unread_mark'] and not row['pinned']     # архив снимает закреп
    assert item['tabs']['archive']['ids'] == [t.pk] and item['tabs']['all']['ids'] == []
    call(client, 'post', f'/api/v1/chat/{t.pk}/draft/', {'text': 'черновик'}, token=ta)
    assert call(client, 'get', '/api/v1/chat/', token=ta).json()['items'][0]['draft'] == 'черновик'
    assert call(client, 'get', f'/api/v1/chat/{t.pk}/', token=ta).json()['thread']['draft'] == 'черновик'
    assert call(client, 'post', f'/api/v1/chat/{t.pk}/state/hide/', token=ta).status_code == 200
    assert call(client, 'get', '/api/v1/chat/', token=ta).json()['items'] == []
    assert len(call(client, 'get', '/api/v1/chat/', token=tb).json()['items']) == 1
    stranger = token_for(User.objects.create_user('c', 'c@x.com', 'x'))
    assert call(client, 'post', f'/api/v1/chat/{t.pk}/state/pin/', token=stranger).status_code == 403


def test_message_actions(client, two):
    _a, _b, ta, tb, t = two
    first = call(client, 'post', f'/api/v1/chat/{t.pk}/send/', {'body': 'Когда **встреча**?'}, token=ta).json()
    reply = call(client, 'post', f'/api/v1/chat/{t.pk}/send/', {'body': 'В пять', 'reply_to': first['id']}, token=tb).json()
    assert reply['reply']['id'] == first['id'] and reply['reply']['name'] == 'Али'
    # правка, исходный текст, реакция, закреп
    assert call(client, 'post', f'/api/v1/chat/msg/{first["id"]}/raw/', token=ta).json()['body'] == 'Когда **встреча**?'
    e = call(client, 'post', f'/api/v1/chat/msg/{reply["id"]}/edit/', {'body': 'В шесть'}, token=tb).json()
    assert e['body'] == 'В шесть' and e['edited']
    assert call(client, 'post', f'/api/v1/chat/msg/{reply["id"]}/edit/', {'body': 'x'}, token=ta).status_code == 403
    rx = call(client, 'post', f'/api/v1/chat/msg/{reply["id"]}/react/', {'emoji': '👍'}, token=ta).json()
    assert rx == {'id': reply['id'], 'reactions': [{'e': '👍', 'n': 1}], 'my_reaction': '👍'}
    assert call(client, 'post', f'/api/v1/chat/msg/{first["id"]}/pin/', token=tb).json()['pinned']
    page = call(client, 'get', f'/api/v1/chat/{t.pk}/', token=ta).json()
    assert [p['id'] for p in page['thread']['pins']] == [first['id']]
    mine = next(m for m in page['items'] if m['id'] == reply['id'])
    assert mine['my_reaction'] == '👍' and mine['reply']['text'] == 'Когда встреча?'
    assert page['thread']['reactions'] and page['thread']['can_pin'] and page['thread']['edit_hours'] == 48
    # поиск и «окно»
    assert [x['id'] for x in call(client, 'get', f'/api/v1/chat/{t.pk}/search/', {'q': 'шесть'}, token=ta).json()['items']] == [reply['id']]
    win = call(client, 'get', f'/api/v1/chat/{t.pk}/', {'around': first['id']}, token=ta).json()
    assert [m['id'] for m in win['items']] == [first['id'], reply['id']]
    # удалить у себя / у всех
    assert call(client, 'post', f'/api/v1/chat/msg/{reply["id"]}/hide/', token=ta).status_code == 200
    assert len(call(client, 'get', f'/api/v1/chat/{t.pk}/', token=ta).json()['items']) == 1
    assert len(call(client, 'get', f'/api/v1/chat/{t.pk}/', token=tb).json()['items']) == 2
    assert call(client, 'post', f'/api/v1/chat/msg/{reply["id"]}/delete/', token=ta).status_code == 403


def test_forward_and_saved(client, two):
    _a, b, ta, _tb, t = two
    m = services.send_text(t, b, 'Адрес: Навои, 1')
    saved = call(client, 'post', '/api/v1/chat/saved/', token=ta).json()['thread']
    r = call(client, 'post', '/api/v1/chat/forward/', {'ids': [m['id']], 'to': ['saved']}, token=ta).json()
    assert r['count'] == 1 and r['threads'] == [saved]
    page = call(client, 'get', f'/api/v1/chat/{saved}/', token=ta).json()
    assert page['thread']['saved'] and page['thread']['title'] == 'Избранное'
    assert page['items'][0]['fwd'] == {'name': 'Биляль', 'user': b.pk, 'room': None}
    row = next(x for x in call(client, 'get', '/api/v1/chat/', token=ta).json()['items'] if x['id'] == saved)
    assert row['saved'] and row['unread'] == 0
    assert call(client, 'post', '/api/v1/chat/forward/', {'ids': [m['id']], 'to': []}, token=ta).status_code == 400


def test_channel_comments_api(client, two):
    a, b, ta, tb, _t = two
    channel = rooms.create(a, Thread.CHANNEL, 'Канал', is_public=True, handle='kanal_api')
    post = services.send_text(channel, a, 'Новость')
    url = f'/api/v1/chat/{channel.pk}/post/{post["id"]}/'
    assert call(client, 'get', url, token=tb).status_code == 404                     # комментарии выключены
    call(client, 'post', f'/api/v1/chat/{channel.pk}/room/', {'comments_on': '1', 'title': 'Канал'}, token=ta)
    assert call(client, 'post', url, {'body': 'без подписки'}, token=tb).status_code == 403
    rooms.join(channel, b)
    r = call(client, 'post', url, {'body': 'ДжазакаЛлаху хайран'}, token=tb).json()
    assert [m['body'] for m in r['items']] == ['ДжазакаЛлаху хайран'] and r['can_write']
    feed = call(client, 'get', f'/api/v1/chat/{channel.pk}/', token=ta).json()
    assert [m['id'] for m in feed['items']] == [post['id']] and feed['items'][0]['comments'] == 1
    assert feed['thread']['comments'] is True


def test_profile_photos(client, two):
    a, _b, ta, tb, _t = two
    assert call(client, 'get', '/api/v1/me/photos/', token=ta).json()['items'] == []
    r1 = client.post('/api/v1/me/photos/', {'photo': jpeg('one.jpg')}, HTTP_AUTHORIZATION=f'Bearer {ta}').json()
    r2 = client.post('/api/v1/me/photos/', {'photo': jpeg('two.jpg')}, HTTP_AUTHORIZATION=f'Bearer {ta}').json()
    assert len(r1['items']) == 1 and len(r2['items']) == 2 and r2['avatar'] == r2['items'][0]['url']
    old = r2['items'][1]['id']
    r3 = call(client, 'post', '/api/v1/me/photos/', {'main': old}, token=ta).json()
    assert r3['items'][0]['id'] == old and r3['avatar'] == r3['items'][0]['url']
    # другой человек видит обе фотографии в профиле
    seen = call(client, 'get', f'/api/v1/users/{a.pk}/', token=tb).json()
    assert len(seen['photos']) == 2 and seen['avatar'] == seen['photos'][0]['url']
    r4 = call(client, 'post', '/api/v1/me/photos/', {'delete': old}, token=ta).json()
    assert len(r4['items']) == 1 and r4['avatar'] == r4['items'][0]['url']
    assert call(client, 'post', '/api/v1/me/photos/', {'delete': r4['items'][0]['id']}, token=tb).status_code == 404


def test_privacy_forward_and_invite(client, two):
    a, b, ta, _tb, _t = two
    r = call(client, 'patch', '/api/v1/me/', {'forward_privacy': 'nobody', 'invite_privacy': 'nobody'}, token=ta).json()
    assert r['privacy']['forward'] == 'nobody' and r['privacy']['invite'] == 'nobody'
    group = rooms.create(b, Thread.GROUP, 'Группа Б')
    a.refresh_from_db()
    assert rooms.add_members(group, b, [a]) == 0                     # запретил добавлять себя в группы
    a.invite_privacy = 'all'
    a.save()
    assert rooms.add_members(group, b, [a]) == 1
