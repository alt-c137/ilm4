"""Группы и каналы: создание, вступление по ссылке, кто может писать, роли, непрочитанное,
удаление сообщений, каталог, выключатели в админке, API приложения."""
import json

import pytest
from django.contrib.auth import get_user_model

from apps.chat import rooms, services
from apps.chat.models import Message, Thread
from apps.core.models import ModuleConfig, SiteSettings

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def people(db):
    ModuleConfig.objects.update_or_create(key='chat', defaults={'name': 'Чат', 'status': 'on'})
    return [User.objects.create_user(n, f'{n}@x.com', 'x', nickname=n.title()) for n in ('imam', 'ali', 'umar', 'zayd')]


def test_group_everyone_writes_and_sees_sender_names(people, client):
    imam, ali, umar, _z = people
    g = rooms.create(imam, 'group', 'Община Ташкента', 'Соседи')
    assert g.kind == 'group' and g.members_count == 1 and rooms.role_of(g, imam) == 'owner'
    # закрытая группа: без ссылки не попасть, со ссылкой — да
    with pytest.raises(services.ChatError):
        rooms.join(g, ali)
    client.force_login(ali)
    assert client.get(f'/chat/{g.pk}/').status_code == 302                      # чужая закрытая группа не видна
    page = client.get(f'/chat/join/{g.invite_code}/')
    assert page.status_code == 200 and 'Община Ташкента' in page.content.decode()
    assert client.post(f'/chat/join/{g.invite_code}/').status_code == 302
    rooms.join(g, umar, g.invite_code)
    g.refresh_from_db()
    assert g.members_count == 3
    services.send_text(g, ali, 'Ассаляму алейкум всем')
    services.send_text(g, imam, 'Ва алейкум ассалям')
    client.force_login(umar)
    html = client.get(f'/chat/{g.pk}/').content.decode()
    assert 'bub__who' in html and 'Ali' in html and 'участников' in html
    assert 'data-call="audio"' not in html                                             # звонков в группе нет
    # список чатов: группа в папке «Группы», непрочитанное считается по участнику
    assert client.get(f'/chat/{g.pk}/').status_code == 200
    services.send_text(g, ali, 'ещё одно')
    row = next(r for r in services.inbox(umar) if r[0].pk == g.pk)
    assert row[0].unread == 1 and row[0].folder == 'groups' and row[1] is None
    rooms.mark_read(g, umar)
    assert next(r for r in services.inbox(umar) if r[0].pk == g.pk)[0].unread == 0


def test_channel_only_admins_post_and_views_are_counted(people, client):
    imam, ali, umar, _z = people
    ch = rooms.create(imam, 'channel', 'Мечеть «Нур»', 'Объявления', is_public=True, handle='masjid_nur')
    assert client.get('/c/masjid_nur/').status_code == 200                      # адрес канала виден и без входа
    client.force_login(ali)
    assert client.get('/c/masjid_nur/').status_code == 302
    page = client.get(f'/chat/{ch.pk}/').content.decode()                       # предпросмотр публичного канала
    assert 'Подписаться' in page and 'name="body"' not in page
    client.post(f'/chat/{ch.pk}/room/join/')
    assert rooms.role_of(ch, ali) == 'member'
    with pytest.raises(services.ChatError):
        services.send_text(ch, ali, 'я подписчик')
    services.send_text(ch, imam, 'Джума в 13:00')
    post = Message.objects.get(thread=ch)
    assert post.views == 0
    client.get(f'/chat/{ch.pk}/')                                               # подписчик открыл канал
    client.get(f'/chat/{ch.pk}/')                                               # второй раз — не считается
    post.refresh_from_db()
    assert post.views == 1
    # владелец назначает админа — тот может писать
    rooms.set_admin(ch, imam, ali, True)
    services.send_text(ch, ali, 'Урок таджвида в субботу')
    with pytest.raises(services.ChatError):
        rooms.set_admin(ch, ali, umar, True)                                    # админ админов не назначает
    # каталог и поиск
    assert [t.pk for t in rooms.catalog('Нур')] == [ch.pk]
    assert 'Мечеть' in client.get('/chat/channels/?q=masjid').content.decode()


def test_handle_rules(people):
    imam = people[0]
    with pytest.raises(services.ChatError):
        rooms.create(imam, 'channel', 'Без имени', is_public=True)
    with pytest.raises(services.ChatError):
        rooms.create(imam, 'channel', 'Плохое имя', is_public=True, handle='ab')
    with pytest.raises(services.ChatError):
        rooms.create(imam, 'channel', 'Занятое слово', is_public=True, handle='admin')
    rooms.create(imam, 'channel', 'Первый', is_public=True, handle='Good_Name')
    with pytest.raises(services.ChatError):
        rooms.create(imam, 'channel', 'Второй', is_public=True, handle='good_name')


def test_remove_ban_leave_and_owner_handover(people):
    imam, ali, umar, _z = people
    g = rooms.create(imam, 'group', 'Группа')
    rooms.join(g, ali, g.invite_code)
    rooms.join(g, umar, g.invite_code)
    rooms.remove_member(g, imam, umar)
    assert not services.is_participant(g, umar)
    with pytest.raises(services.ChatError):
        rooms.join(g, umar, g.invite_code)                                      # удалённый по ссылке не вернётся
    with pytest.raises(services.ChatError):
        rooms.remove_member(g, ali, imam)                                       # участник никого не удаляет
    old = g.invite_code
    assert rooms.reset_invite(g, imam) != old and rooms.by_code(old) is None
    rooms.leave(g, imam)                                                        # владелец ушёл — группа переходит дальше
    assert rooms.role_of(g, ali) == 'owner'
    rooms.leave(g, ali)                                                         # последний ушёл — группы нет
    assert not Thread.objects.filter(pk=g.pk).exists()


def test_add_only_people_you_already_talk_to(people):
    imam, ali, umar, _z = people
    g = rooms.create(imam, 'group', 'Группа')
    services.open_direct(imam, ali)
    assert rooms.add_members(g, imam, [ali, umar]) == 1                         # с Умаром переписки нет — не добавлен
    assert services.is_participant(g, ali) and not services.is_participant(g, umar)


def test_delete_message_author_and_admin(people, client):
    imam, ali, umar, _z = people
    g = rooms.create(imam, 'group', 'Группа')
    rooms.join(g, ali, g.invite_code)
    rooms.join(g, umar, g.invite_code)
    mine = Message.objects.get(pk=services.send_text(g, ali, 'моё')['id'])
    other = Message.objects.get(pk=services.send_text(g, umar, 'чужое')['id'])
    client.force_login(ali)
    assert client.post(f'/chat/msg/{other.pk}/delete/').status_code == 403      # чужое участник не удалит
    assert client.post(f'/chat/msg/{mine.pk}/delete/').status_code == 200
    client.force_login(imam)
    assert client.post(f'/chat/msg/{other.pk}/delete/').status_code == 200      # админ удаляет любое
    assert not Message.objects.filter(thread=g).exists()
    # личный диалог: только своё
    t = services.open_direct(ali, umar)
    m = Message.objects.get(pk=services.send_text(t, umar, 'привет')['id'])
    client.force_login(ali)
    assert client.post(f'/chat/msg/{m.pk}/delete/').status_code == 403


def test_admin_switches_hide_rooms(people, client):
    imam, ali, _u, _z = people
    g = rooms.create(imam, 'group', 'Группа', is_public=True, handle='our_group')
    ch = rooms.create(imam, 'channel', 'Канал', is_public=True, handle='our_channel')
    st = SiteSettings.get_solo()
    st.chat_channels_enabled = False
    st.save()
    client.force_login(imam)
    assert client.get(f'/chat/{ch.pk}/').status_code == 302 and client.get('/c/our_channel/').status_code == 404
    assert [r[0].pk for r in services.inbox(imam)] == [g.pk]                    # канал пропал из списка
    assert client.get('/chat/new/?kind=channel').status_code == 200             # группу создать ещё можно
    assert 'Новая группа' in client.get('/chat/new/?kind=channel').content.decode()
    st.chat_channels_enabled, st.chat_channels_staff_only = True, True
    st.save()
    with pytest.raises(services.ChatError):
        rooms.create(ali, 'channel', 'Мой канал')                               # каналы — только сотрудникам
    st.chat_groups_enabled = False
    st.save()
    with pytest.raises(services.ChatError):
        rooms.create(ali, 'group', 'Моя группа')


def test_moderator_can_close_and_verify(people, client):
    imam, ali, _u, _z = people
    ch = rooms.create(imam, 'channel', 'Канал', is_public=True, handle='some_channel')
    from django_otp.plugins.otp_totp.models import TOTPDevice
    staff = User.objects.create_superuser('boss', 'boss@x.com', 'x')
    client.force_login(ali)
    assert client.post(f'/chat/{ch.pk}/room/close/').status_code == 404         # обычному человеку — нельзя
    client.force_login(staff)
    session = client.session                                                    # сотрудник с подтверждённой 2FA
    session['otp_device_id'] = TOTPDevice.objects.create(user=staff, name='t', confirmed=True).persistent_id
    session.save()
    client.post(f'/chat/{ch.pk}/room/verify/')
    client.post(f'/chat/{ch.pk}/room/close/')
    ch.refresh_from_db()
    assert ch.platform_verified and ch.closed
    with pytest.raises(services.ChatError):
        services.send_text(ch, imam, 'после закрытия')
    assert not list(rooms.catalog())


def test_rooms_api_for_app(people, client):
    from apps.api.models import ApiToken
    imam, ali, _u, _z = people
    a_imam = {'HTTP_AUTHORIZATION': 'Bearer ' + ApiToken.issue(imam)}
    a_ali = {'HTTP_AUTHORIZATION': 'Bearer ' + ApiToken.issue(ali)}
    r = client.post('/api/v1/chat/rooms/new/', json.dumps({'kind': 'channel', 'title': 'Уроки таджвида', 'is_public': True,
                                                            'handle': 'tajwid'}), content_type='application/json', **a_imam)
    assert r.status_code == 200, r.content
    pk = r.json()['thread']
    cat = client.get('/api/v1/chat/rooms/?q=тадж', **a_ali).json()
    assert cat['items'][0]['title'] == 'Уроки таджвида' and cat['items'][0]['member'] is False
    assert client.get('/api/v1/chat/c/tajwid/', **a_ali).json()['id'] == pk
    joined = client.post(f'/api/v1/chat/{pk}/room/join/', **a_ali).json()
    assert joined['member'] and joined['members'] == 2 and joined['can_post'] is False
    client.post(f'/api/v1/chat/{pk}/send/', json.dumps({'body': 'Урок 1'}), content_type='application/json', **a_imam)
    assert client.post(f'/api/v1/chat/{pk}/send/', json.dumps({'body': 'я'}), content_type='application/json', **a_ali).status_code == 403
    lst = client.get('/api/v1/chat/', **a_ali).json()
    item = lst['items'][0]
    assert item['room'] == 'channel' and item['title'] == 'Уроки таджвида' and item['unread'] == 1 and item['folder'] == 'channels'
    msgs = client.get(f'/api/v1/chat/{pk}/', **a_ali).json()
    assert msgs['thread']['room']['kind'] == 'channel' and msgs['items'][0]['room'] == 'channel'
    assert msgs['thread']['room']['public_link'].endswith('/c/tajwid/')
    assert client.post(f'/api/v1/chat/{pk}/room/mute/', **a_ali).json()['muted'] is True
    info = client.get(f'/api/v1/chat/{pk}/room/', **a_imam).json()
    assert [p['role'] for p in info['people']] == ['owner', 'member']
    assert client.post(f'/api/v1/chat/{pk}/member/{ali.pk}/admin/', **a_imam).json()['people'][1]['role'] == 'admin'
    assert client.post(f'/api/v1/chat/{pk}/room/leave/', **a_ali).json()['left'] is True
    mid = msgs['items'][0]['id']
    assert client.post(f'/api/v1/chat/msg/{mid}/delete/', **a_imam).json()['ok'] is True
