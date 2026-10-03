"""«Как в Telegram»: свои папки, архив, закреп, «не прочитано», черновик, очистка истории;
ответ, правка, пересылка, закреп сообщений, реакции, поиск, «Избранное», комментарии к постам."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.chat import rooms, services
from apps.chat.models import ChatFolder, ChatState, Message, Thread
from apps.chat.services import ChatError

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def world(db):
    from apps.core.models import ModuleConfig, SiteSettings
    ModuleConfig.objects.update_or_create(key='chat', defaults={'name': 'Чат', 'status': 'on'})
    st = SiteSettings.get_solo()
    st.chat_groups_enabled = st.chat_channels_enabled = True
    st.phone_for_publish = False
    st.save()
    a = User.objects.create_user('a', 'a@x.com', 'x', first_name='Али')
    b = User.objects.create_user('b', 'b@x.com', 'x', first_name='Биляль')
    c = User.objects.create_user('c', 'c@x.com', 'x', first_name='Салих')
    return a, b, c


def _threads(user):
    rows = services.inbox(user)
    return [t for t, _o, _m in rows]


def _folder_ids(user, folder):
    data = services.folder_summary(user, _threads(user))
    return next(f for f in data['folders'] if f['id'] == folder.pk)['ids']


# ---------- папки ----------

def test_folder_by_types_and_manual_chats(world):
    a, b, _c = world
    direct = services.open_direct(a, b)
    group = rooms.create(a, Thread.GROUP, 'Учим арабский')
    channel = rooms.create(a, Thread.CHANNEL, 'Новости мечети')
    services.send_text(direct, b, 'салам')

    people = services.save_folder(a, {'title': 'Личное', 'types': ['personal']})
    assert _folder_ids(a, people) == [direct.pk]

    mine = services.save_folder(a, {'title': 'Моё', 'types': ['groups'], 'include': [channel.pk]})
    assert set(_folder_ids(a, mine)) == {group.pk, channel.pk}

    # исключить поимённо
    services.set_folder_chat(a, mine.pk, group, False)
    assert _folder_ids(a, mine) == [channel.pk]
    services.set_folder_chat(a, mine.pk, group, True)
    assert set(_folder_ids(a, mine)) == {group.pk, channel.pk}


def test_folder_excludes_read_muted_archived(world):
    a, b, c = world
    t1, t2 = services.open_direct(a, b), services.open_direct(a, c)
    services.send_text(t1, b, 'новое')                     # непрочитанное у a
    services.send_text(t2, a, 'моё')                       # у a непрочитанного нет
    unread = services.save_folder(a, {'title': 'Новые', 'types': ['personal'], 'no_read': '1'})
    assert _folder_ids(a, unread) == [t1.pk]
    services.set_unread(t2, a, True)                       # «пометить непрочитанным» — попадает в папку
    assert set(_folder_ids(a, unread)) == {t1.pk, t2.pk}

    loud = services.save_folder(a, {'title': 'Со звуком', 'types': ['personal'], 'no_muted': '1'})
    services.set_muted(t1, a, True)
    assert _folder_ids(a, loud) == [t2.pk]

    services.set_archived(t2, a, True)
    assert _folder_ids(a, loud) == []                       # архив по умолчанию исключён
    summary = services.folder_summary(a, _threads(a))
    assert summary['archive']['ids'] == [t2.pk] and t2.pk not in summary['all']['ids']


def test_folder_limits_order_and_recommended(world):
    a, b, _c = world
    services.open_direct(a, b)
    rec = services.recommended_folders(a)
    assert {r['key'] for r in rec} == {'unread', 'personal', 'ads', 'rooms'}
    made = [services.save_folder(a, {'title': f'Папка {i}', 'types': ['personal']}) for i in range(ChatFolder.MAX_FOLDERS)]
    with pytest.raises(ChatError):
        services.save_folder(a, {'title': 'Лишняя', 'types': ['personal']})
    with pytest.raises(ChatError):
        services.save_folder(a, {'title': '', 'types': ['personal']}, made[0])
    services.reorder_folders(a, [made[2].pk, made[0].pk])
    assert [f.pk for f in services.user_folders(a)][:2] == [made[2].pk, made[0].pk]
    services.delete_folder(a, made[0].pk)
    assert len(services.user_folders(a)) == ChatFolder.MAX_FOLDERS - 1
    # чужую папку не тронуть
    services.delete_folder(b, made[1].pk)
    assert ChatFolder.objects.filter(pk=made[1].pk).exists()


def test_empty_folder_refused(world):
    a, _b, _c = world
    with pytest.raises(ChatError):
        services.save_folder(a, {'title': 'Пусто', 'types': [], 'include': []})


# ---------- состояние чата ----------

def test_pin_limit_and_order(world):
    a, _b, _c = world
    others = [User.objects.create_user(f'u{i}', f'u{i}@x.com', 'x') for i in range(6)]
    threads = [services.open_direct(a, u) for u in others]
    for t in threads[:5]:
        services.set_pinned(t, a, True)
    with pytest.raises(ChatError):
        services.set_pinned(threads[5], a, True)
    first = _threads(a)[0]
    assert first.pk == threads[4].pk and first.pinned_at          # закрепил позже — выше
    services.set_pinned(threads[4], a, False)
    services.set_pinned(threads[5], a, True)
    # в своей папке — закреп отдельный и без ограничения
    f = services.save_folder(a, {'title': 'Все', 'types': ['personal']})
    services.set_pinned(threads[0], a, True, folder=f)
    f.refresh_from_db()
    assert f.pins == [threads[0].pk]
    # собеседник ничего этого не видит
    assert not ChatState.objects.filter(user=others[0]).exists()


def test_archive_pops_out_on_new_message_unless_muted(world):
    a, b, c = world
    t1, t2 = services.open_direct(a, b), services.open_direct(a, c)
    services.set_archived(t1, a, True)
    services.set_archived(t2, a, True)
    services.set_muted(t2, a, True)
    services.send_text(t1, b, 'ты тут?')
    services.send_text(t2, c, 'ау')
    assert not ChatState.objects.get(thread=t1, user=a).archived      # всплыл
    assert ChatState.objects.get(thread=t2, user=a).archived          # «без звука» — остаётся в архиве


def test_clear_history_and_hide_chat_only_for_me(world):
    a, b, _c = world
    t = services.open_direct(a, b)
    services.send_text(t, a, 'раз')
    services.send_text(t, b, 'два')
    services.clear_history(t, a)
    assert services.visible_messages(t, a).count() == 0
    assert services.visible_messages(t, b).count() == 2
    services.hide_chat(t, a)
    assert t.pk not in [x.pk for x in _threads(a)]
    assert t.pk in [x.pk for x in _threads(b)]
    services.send_text(t, b, 'три')                                   # новое сообщение возвращает чат
    mine = _threads(a)
    assert [x.pk for x in mine] == [t.pk] and mine[0].unread == 1
    assert [m.body for m in services.visible_messages(t, a)] == ['три']


def test_draft_is_private_and_encrypted(world):
    a, b, _c = world
    t = services.open_direct(a, b)
    services.set_draft(t, a, 'недописал')
    st = ChatState.objects.get(thread=t, user=a)
    assert 'недописал' not in st.draft_enc
    assert _threads(a)[0].draft == 'недописал' and _threads(b)[0].draft == ''
    services.set_draft(t, a, '')
    assert _threads(a)[0].draft == ''


def test_state_only_for_participants(world):
    a, b, c = world
    t = services.open_direct(a, b)
    for fn in (lambda: services.set_pinned(t, c, True), lambda: services.set_archived(t, c, True),
               lambda: services.clear_history(t, c), lambda: services.hide_chat(t, c)):
        with pytest.raises(ChatError):
            fn()


# ---------- сообщения ----------

def test_reply_edit_and_edit_window(world):
    a, b, c = world
    t = services.open_direct(a, b)
    first = services.send_text(t, a, 'Когда встретимся?')
    answer = services.send_text(t, b, 'Завтра', reply_to=first['id'])
    assert answer['reply']['id'] == first['id'] and answer['reply']['text'] == 'Когда встретимся?'
    # ответ на сообщение из чужого чата не привязывается
    other = services.send_text(services.open_direct(a, c), a, 'секрет')
    assert services.send_text(t, b, 'ок', reply_to=other['id'])['reply'] is None

    edited = services.edit_message(b, answer['id'], 'Послезавтра')
    assert edited['body'] == 'Послезавтра' and edited['edited']
    with pytest.raises(ChatError):
        services.edit_message(a, answer['id'], 'чужое')
    Message.objects.filter(pk=answer['id']).update(created_at=timezone.now() - timedelta(hours=49))
    with pytest.raises(ChatError):
        services.edit_message(b, answer['id'], 'поздно')


def test_delete_for_me_and_for_all(world):
    a, b, _c = world
    t = services.open_direct(a, b)
    m = services.send_text(t, b, 'чужое сообщение')
    with pytest.raises(ChatError):
        services.delete_message(a, m['id'])                      # чужое у всех удалить нельзя
    services.delete_message(a, m['id'], for_all=False)
    assert services.visible_messages(t, a).count() == 0 and services.visible_messages(t, b).count() == 1
    services.delete_message(b, m['id'])
    assert not Message.objects.filter(pk=m['id']).exists()


def test_reactions_one_per_person(world):
    a, b, c = world
    t = services.open_direct(a, b)
    m = services.send_text(t, a, 'Альхамдулиллях')
    assert services.react(b, m['id'], '🤲') == {'id': m['id'], 'reactions': [{'e': '🤲', 'n': 1}], 'my_reaction': '🤲'}
    assert services.react(b, m['id'], '❤️')['reactions'] == [{'e': '❤️', 'n': 1}]      # заменил
    services.react(a, m['id'], '❤️')
    assert services.react(b, m['id'], '❤️')['reactions'] == [{'e': '❤️', 'n': 1}]      # повтор — снял
    with pytest.raises(ChatError):
        services.react(b, m['id'], '💩')
    with pytest.raises(ChatError):
        services.react(c, m['id'], '👍')                         # посторонний


def test_pin_messages(world):
    a, b, _c = world
    t = services.open_direct(a, b)
    m1, m2 = services.send_text(t, a, 'адрес: ул. Навои, 1'), services.send_text(t, b, 'время: 18:00')
    services.pin_message(b, m1['id'])
    services.pin_message(a, m2['id'])
    assert [m.pk for m in services.pinned_messages(t, a)] == [m1['id'], m2['id']]
    services.pin_message(a, m1['id'], False)
    assert [m.pk for m in services.pinned_messages(t, b)] == [m2['id']]
    group = rooms.create(a, Thread.GROUP, 'Группа')
    rooms.join(group, b, group.invite_code)
    gm = services.send_text(group, b, 'привет')
    with pytest.raises(ChatError):
        services.pin_message(b, gm['id'])                        # в группе закрепляют админы
    assert services.pin_message(a, gm['id'])['pinned']


def test_forward_text_and_file_reencrypted(world, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    a, b, c = world
    src, dst = services.open_direct(a, b), services.open_direct(a, c)
    text = services.send_text(src, b, 'Перешли это')
    doc = services.store_upload(src, b, 'file', SimpleUploadedFile('план.txt', b'secret plan ' * 100))
    out = services.forward_messages(a, [text['id'], doc['id']], [dst.pk, 'saved'])
    assert len(out) == 4
    copies = list(Message.objects.filter(thread=dst).order_by('pk'))
    assert copies[0].body == 'Перешли это' and copies[0].fwd['name'] == 'Биляль' and copies[0].fwd['user'] == b.pk
    assert copies[1].meta['name'] == 'план.txt'
    # файл перешифрован ключом нового чата: читается в нём и совпадает с исходным
    from apps.chat import filecrypt
    with copies[1].attachment.open('rb') as fh:
        r = filecrypt.Reader(dst.pk, fh, copies[1].attachment.size)
        assert b''.join(r.iter_range(0, r.size - 1)) == b'secret plan ' * 100
    saved = services.open_saved(a)
    assert saved.is_saved and Message.objects.filter(thread=saved).count() == 2
    # скрыть автора; своё сообщение пересылается без «от кого»
    hidden = services.forward_messages(a, [text['id']], [dst.pk], hide_sender=True)
    assert hidden[0]['fwd'] is None
    own = services.send_text(src, a, 'моё')
    assert services.forward_messages(a, [own['id']], [dst.pk])[0]['fwd'] is None
    # приватность пересылки: без ссылки на профиль
    b.forward_privacy = 'nobody'
    b.save()
    again = services.forward_messages(a, [text['id']], [dst.pk])
    assert again[0]['fwd'] == {'name': 'Биляль', 'user': None, 'room': None}


def test_forward_respects_access_and_protection(world):
    a, b, c = world
    src = services.open_direct(a, b)
    m = services.send_text(src, a, 'не для всех')
    with pytest.raises(ChatError):
        services.forward_messages(c, [m['id']], ['saved'])       # чужой чат
    group = rooms.create(a, Thread.GROUP, 'Закрытая')
    rooms.update(group, a, {'protected': '1'})
    gm = services.send_text(group, a, 'только здесь')
    with pytest.raises(ChatError):
        services.forward_messages(a, [gm['id']], ['saved'])
    with pytest.raises(ChatError):
        services.forward_messages(a, [m['id']], [services.open_direct(b, c).pk])   # туда писать нельзя


def test_search_and_window(world):
    a, b, _c = world
    t = services.open_direct(a, b)
    ids = [services.send_text(t, a if i % 2 else b, f'сообщение номер {i}')['id'] for i in range(30)]
    services.send_text(t, a, 'Купил ХАЛЯЛЬ мясо')
    found = services.search_messages(t, b, 'халяль')
    assert len(found) == 1 and 'мясо' in found[0].body
    assert services.search_messages(t, b, 'х') == []
    win = services.window_around(t, a, ids[15], half=5)
    assert [m.pk for m in win['items']] == ids[10:21] and win['more_before'] and win['more_after']


def test_saved_messages(world):
    a, _b, _c = world
    saved = services.open_saved(a)
    assert services.open_saved(a).pk == saved.pk
    services.send_text(saved, a, 'заметка')
    rows = services.inbox(a)
    assert rows[0][0].is_saved and rows[0][1] is None and rows[0][0].unread == 0


def test_channel_comments(world):
    a, b, c = world
    channel = rooms.create(a, Thread.CHANNEL, 'Канал', is_public=True, handle='kanal_test')
    post = services.send_text(channel, a, 'Пятничная хутба — в 13:00')
    with pytest.raises(ChatError):
        services.add_comment(b, post['id'], 'ДжазакаЛлаху хайран')      # комментарии выключены
    rooms.update(channel, a, {'comments_on': '1'})
    with pytest.raises(ChatError):
        services.add_comment(b, post['id'], 'не подписан')
    rooms.join(channel, b)
    first = services.add_comment(b, post['id'], 'ДжазакаЛлаху хайран')
    assert first['comment_of'] == post['id']
    data = services.comments_of(c, post['id'])
    assert [m.body for m in data['items']] == ['ДжазакаЛлаху хайран']
    assert Message.objects.get(pk=post['id']).comments_count == 1
    # в ленте канала и в счётчике непрочитанного комментариев нет
    assert [m.pk for m in services.visible_messages(channel, a)] == [post['id']]
    assert next(t for t in _threads(a) if t.pk == channel.pk).unread == 0
    services.delete_message(b, first['id'])
    assert Message.objects.get(pk=post['id']).comments_count == 0


def test_slow_mode(world):
    a, b, _c = world
    group = rooms.create(a, Thread.GROUP, 'Медленная')
    rooms.join(group, b, group.invite_code)
    rooms.update(group, a, {'slow_seconds': '60'})
    services.send_text(group, b, 'раз')
    with pytest.raises(ChatError):
        services.send_text(group, b, 'два')
    services.send_text(group, a, 'админу можно')
    services.send_text(group, a, 'и ещё')


def test_mention_reaches_muted_member(world):
    a, b, _c = world
    group = rooms.create(a, Thread.GROUP, 'Упоминания')
    rooms.join(group, b, group.invite_code)
    b.handle = 'bilal_x'
    b.save()
    msg = Message.objects.create(thread=group, sender=a, body='@bilal_x посмотри, и @nobody_here тоже')
    assert services._must_notify(group, msg) == {b.pk}
    first = Message.objects.create(thread=group, sender=b, body='вопрос')
    reply = Message.objects.create(thread=group, sender=a, body='ответ', reply_to=first)
    assert services._must_notify(group, reply) == {b.pk}


def test_nikah_chat_hides_main_profile(client, world):
    """Маска: в чате никяха собеседник видит имя из анкеты, а не основной профиль (@имя, лента, объявления)."""
    from apps.api.models import ApiToken
    from apps.chat import persona
    from apps.nikah.models import NikahProfile
    a, b, _c = world
    NikahProfile.objects.create(user=b, name='Умм Хабиба', gender='F', age=25, age_from=20, age_to=40)
    t = services.open_private_thread([a, b], subject='Никях · знакомство', context=('nikah', 1))
    services.send_text(t, b, 'Ассаляму алейкум')
    assert persona.name_in(t, b) == 'Умм Хабиба' and persona.name_in(t, a) == 'Анкета никяха'
    client.force_login(a)
    html = client.get(f'/chat/{t.pk}/').content.decode()
    assert 'Умм Хабиба' in html and f'/accounts/u/{b.pk}/' not in html and b.get_display_name() not in html
    row = client.get('/api/v1/chat/', HTTP_AUTHORIZATION=f'Bearer {ApiToken.issue(a, "t")}').json()['items'][0]
    assert row['title'] == 'Умм Хабиба' and row['other_id'] is None and row['avatar'] == ''
    ordinary = services.open_direct(a, b)                      # обычный чат тех же людей — обычный профиль
    assert persona.name_in(ordinary, b) == b.get_display_name()
