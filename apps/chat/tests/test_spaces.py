"""Сообщества (как Discord): каналы-чаты, вступление, роли, свой ник, изоляция от общего списка чатов."""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.chat import persona, rooms, services, spaces
from apps.chat.models import Member, SpaceMember, Thread
from apps.core.models import ModuleConfig

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def people():
    ModuleConfig.objects.update_or_create(key='communities', defaults={'name': 'Сообщества', 'status': 'on'})
    out = []
    for i, name in enumerate(['Али', 'Биляль', 'Умар']):
        out.append(User.objects.create_user(f'sp{i}', f'sp{i}@x.com', 'x', first_name=name, phone=f'+99890111220{i}',
                                            phone_verified_at=timezone.now()))
    return out


def test_create_join_and_channels(people):
    a, b, c = people
    s = spaces.create(a, 'Айтишники', 'код и работа', is_public=True)
    kinds = sorted(t.kind for t in s.threads.all())
    assert kinds == [Thread.CHANNEL, Thread.GROUP] and s.voices.count() == 1                 # объявления + общий + голосовая (основа)
    general = s.threads.get(kind=Thread.GROUP)
    news = s.threads.get(kind=Thread.CHANNEL)
    spaces.join(s, b)
    assert services.can_read(general, b) and not services.can_read(general, c)
    services.send_text(general, b, 'салам')
    with pytest.raises(services.ChatError):
        services.send_text(news, b, 'я не админ')                                            # объявления пишут админы
    # каналы сообщества не попадают в общий список чатов — только внутрь сообщества
    assert [t.pk for t, _o, _m in services.inbox(a)] == []
    tree = spaces.tree(s, a)
    assert tree['unread'] == 1 and tree['first'] in (general.pk, news.pk)
    # новый канал сразу получают все участники; уведомления — только по упоминанию (без звука)
    extra = spaces.add_channel(s, a, 'вакансии')
    assert services.can_read(extra, b) and Member.objects.get(thread=extra, user=b).muted
    with pytest.raises(services.ChatError):
        spaces.add_channel(s, b, 'мой канал')                                                # участник каналы не создаёт
    with pytest.raises(services.ChatError):
        rooms.leave(general, b)                                                              # из одного канала не выйти
    assert general not in list(rooms.catalog())
    s.refresh_from_db()
    assert s.members_count == 2


def test_nick_roles_kick(people):
    a, b, c = people
    s = spaces.create(a, 'Клуб', is_public=False)
    with pytest.raises(services.ChatError):
        spaces.join(s, b)                                                                    # закрытое — только по ссылке
    spaces.join(s, b, s.invite_code)
    spaces.join(s, c, s.invite_code)
    general = s.threads.get(kind=Thread.GROUP)
    spaces.set_nick(s, b, 'CyberWolf')
    assert persona.name_in(general, b) == 'CyberWolf' and persona.name_by_thread_id(general.pk, b) == 'CyberWolf'
    assert persona.name_in(general, c) == 'Умар'                                             # без ника — обычное имя
    direct = services.open_direct(a, b)
    assert persona.name_in(direct, b) == 'Биляль'                                            # ник действует только в сообществе
    spaces.set_role(s, a, b, SpaceMember.MOD)
    assert rooms.is_admin(general, b)                                                        # модератор может убирать сообщения
    with pytest.raises(services.ChatError):
        spaces.set_role(s, b, c, SpaceMember.ADMIN)                                          # роли раздаёт админ
    spaces.kick(s, b, c)
    assert not services.can_read(general, c)
    with pytest.raises(services.ChatError):
        spaces.join(s, c, s.invite_code)                                                     # удалённый не возвращается
    spaces.leave(s, a)                                                                       # владелец ушёл — владение переходит
    s.refresh_from_db()
    assert s.owner == b and spaces.membership(s, b).role == SpaceMember.OWNER


def test_pages(client, people):
    a, b, _c = people
    s = spaces.create(a, 'Айтишники', is_public=True)
    general = s.threads.get(kind=Thread.GROUP)
    assert 'Айтишники' in client.get('/communities/').content.decode()
    client.force_login(b)
    page = client.get(f'/communities/{s.pk}/').content.decode()
    assert 'Вступить' in page and f'/chat/{general.pk}/' not in page                          # не участник — каналы без ссылок
    client.post(f'/communities/{s.pk}/act/', {'action': 'join'})
    page = client.get(f'/chat/{general.pk}/').content.decode()
    assert 'sp__side' in page and 'tg-list' not in page                                      # слева каналы сообщества, а не список чатов
    client.post(f'/communities/{s.pk}/act/', {'action': 'nick', 'nick': 'Wolf'})
    assert spaces.membership(s, b).nick == 'Wolf'
    assert client.post(f'/communities/{s.pk}/act/', {'action': 'channel', 'title': 'x1'}).status_code == 302
    assert s.threads.count() == 2                                                            # не админ — канал не создался


def test_api(client, people):
    import json

    from apps.api.models import ApiToken
    a, b, _c = people
    ha = {'HTTP_AUTHORIZATION': f'Bearer {ApiToken.issue(a, "t")}'}
    hb = {'HTTP_AUTHORIZATION': f'Bearer {ApiToken.issue(b, "t")}'}

    def post(url, data, h):
        return client.post(url, json.dumps(data), content_type='application/json', **h)
    sid = post('/api/v1/communities/new/', {'title': 'Клуб книг', 'is_public': True}, ha).json()['id']
    assert client.get('/api/v1/communities/', **hb).json()['catalog'][0]['title'] == 'Клуб книг'
    seen = client.get(f'/api/v1/communities/{sid}/', **hb).json()
    assert seen['me'] is None and seen['people'] == [] and seen['invite'] == ''
    joined = post(f'/api/v1/communities/{sid}/act/', {'action': 'join'}, hb).json()
    assert joined['me']['role'] == 'member' and len(joined['people']) == 2
    assert post(f'/api/v1/communities/{sid}/act/', {'action': 'channel', 'title': 'нельзя'}, hb).status_code == 403
    full = post(f'/api/v1/communities/{sid}/act/', {'action': 'channel', 'title': 'обзоры', 'kind': 'text'}, ha).json()
    names = [ch['title'] for g in full['groups'] for ch in g['channels']]
    assert 'обзоры' in names and full['invite'].endswith('/')
    assert post(f'/api/v1/communities/{sid}/act/', {'action': 'nick', 'nick': 'Читатель'}, hb).json()['me']['nick'] == 'Читатель'
    assert client.get('/api/v1/chat/', **hb).json()['items'] == []          # каналы сообщества — не в общем списке чатов


def test_roles_private_channels_timeouts_invites(people):
    """Как в Discord: свои роли с правами, закрытый канал по роли, тайм-аут, приглашение на одного, @everyone, журнал."""
    from datetime import timedelta

    from apps.chat.models import SpaceInvite
    a, b, c = people
    s = spaces.create(a, 'Школа', is_public=True)
    spaces.join(s, b)
    spaces.join(s, c)
    teacher = spaces.save_role(s, a, name='Учитель', color='#22c55e', perms=['delete_messages', 'mention_everyone'])
    with pytest.raises(services.ChatError):
        spaces.save_role(s, b, name='Самозванец')                                           # ролями управляет не каждый
    staff = spaces.add_channel(s, a, 'учительская', private=True, role_ids=[teacher.pk])
    assert services.can_read(staff, a) and not services.can_read(staff, b)                   # закрытый канал — только по роли
    assert 'учительская' not in [ch['title'] for g in spaces.tree(s, b)['groups'] for ch in g['channels']]
    spaces.set_member_roles(s, a, b, [teacher.pk])
    assert services.can_read(staff, b) and rooms.is_admin(staff, b)                          # роль дала доступ и право удалять сообщения
    assert spaces.can(s, b, 'mention_everyone') and not spaces.can(s, b, 'kick')
    general = s.threads.get(title='общий')
    assert spaces.mention_targets(general, b, 'Сбор в пять, @everyone') == {a.pk, c.pk}
    assert spaces.mention_targets(general, c, '@everyone') == set()                          # без права @everyone никого не будит
    assert spaces.mention_targets(general, c, 'вопрос к @учитель') == {b.pk}                 # упоминание роли
    spaces.delete_role(s, a, teacher.pk)
    assert not services.can_read(staff, b)                                                   # роль удалили — доступ пропал
    # тайм-аут
    spaces.timeout(s, a, c, '1h')
    with pytest.raises(services.ChatError):
        services.send_text(general, c, 'я в тайм-ауте')
    spaces.timeout(s, a, c, '')
    services.send_text(general, c, 'снова могу')
    with pytest.raises(services.ChatError):
        spaces.timeout(s, c, b, '1h')                                                        # участник участнику — нельзя
    # приглашение на одного человека и со сроком
    s.is_public = False
    s.save()
    inv = spaces.create_invite(s, a, hours=1, max_uses=1)
    d = User.objects.create_user('sp9', 'sp9@x.com', 'x')
    e = User.objects.create_user('sp8', 'sp8@x.com', 'x')
    spaces.join(s, d, inv.code)
    with pytest.raises(services.ChatError):
        spaces.join(s, e, inv.code)                                                          # приглашение уже использовано
    late = spaces.create_invite(s, a, hours=1)
    SpaceInvite.objects.filter(pk=late.pk).update(expires_at=late.expires_at - timedelta(hours=2))
    assert spaces.by_code(late.code) is None                                                 # срок вышел
    # удалённого можно вернуть
    spaces.kick(s, a, c)
    spaces.unban(s, a, c)
    spaces.join(s, c, s.invite_code)
    assert s.logs.filter(action='kick').exists() and s.logs.filter(action='role').exists()   # журнал ведётся


def test_task_board(client, people):
    a, b, _c = people
    s = spaces.create(a, 'Проект', is_public=True)
    spaces.join(s, b)
    t = spaces.save_task(s, b, title='Снять ролик о сообществе')
    spaces.move_task(s, a, t.pk, 'doing')
    t.refresh_from_db()
    assert t.status == 'doing' and t.assignee == a                                           # взял в работу — стал исполнителем
    other = spaces.save_task(s, a, title='Только моя')
    with pytest.raises(services.ChatError):
        spaces.delete_task(s, b, other.pk)                                                   # чужую задачу не удалить
    client.force_login(b)
    page = client.get(f'/communities/{s.pk}/board/').content.decode()
    assert 'Снять ролик о сообществе' in page and 'Делаем' in page
    client.post(f'/communities/{s.pk}/board/', {'action': 'move', 'task': t.pk, 'status': 'done'})
    t.refresh_from_db()
    assert t.status == 'done'
    assert client.get(f'/communities/{s.pk}/voice/{s.voices.first().pk}/').status_code == 200
