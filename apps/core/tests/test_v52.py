"""v52: «маски» (профили разделов), закрытый профиль, имя контакта в чатах, общий поиск, главная, настройки сообщества."""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts import people
from apps.api.models import ApiToken
from apps.chat import persona, services, spaces
from apps.core.models import Moderation, ModuleConfig, Report
from apps.social import services as social

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def trio():
    for key, name in (('chat', 'Чат'), ('feed', 'Лента'), ('communities', 'Сообщества'), ('buy', 'Маркет'), ('tracker', 'Трекер')):
        ModuleConfig.objects.update_or_create(key=key, defaults={'name': name, 'status': 'on'})
    return [User.objects.create_user(f'v{i}', f'v{i}@x.com', 'x', first_name=n, handle=h, phone=f'+99890777000{i}', phone_verified_at=timezone.now())
            for i, (n, h) in enumerate([('Али', 'ali_v52'), ('Биляль', 'bilal_v52'), ('Умар', 'umar_v52')])]


def auth(user):
    return {'HTTP_AUTHORIZATION': f'Bearer {ApiToken.issue(user, "t")}'}


def listing(owner):
    from apps.market.models import Category, Listing
    cat = Category.objects.create(name='Еда', slug='food-v52')
    return Listing.objects.create(owner=owner, category=cat, title='Финики аджва', description='1 кг', price=28, city='Ташкент',
                                  status=Moderation.APPROVED)


def test_board_persona_hides_main_profile(client, trio):
    seller, buyer, _c = trio
    item = listing(seller)
    # без маски — обычный профиль
    assert people.face(seller)['id'] == seller.pk and not people.face(seller)['masked']
    people.save_persona(seller, people.BOARD, 'Сладости Самарканда', link_main=False)
    people.save_persona(seller, people.BOARD, 'Сладости Самарканда', link_main=False)        # второй раз — та же маска, не новая
    assert seller.personas.count() == 1                                                    # одна на раздел
    f = people.face(seller)
    assert f == {**f, 'name': 'Сладости Самарканда', 'id': None, 'link': '', 'masked': True}
    # страница объявления: имя маски, нет ни ссылки на профиль, ни номера аккаунта в кнопке «Написать»
    client.force_login(buyer)
    html = client.get(f'/buy/{item.pk}/').content.decode()
    assert 'Сладости Самарканда' in html and f'/accounts/u/{seller.pk}/' not in html and f'user={seller.pk}' not in html
    # чат по объявлению начинается без номера аккаунта продавца; собеседник в нём — под маской
    r = client.get(f'/chat/start/?ctx=buy&ctx_id={item.pk}')
    assert r.status_code == 302
    thread = buyer.chat_threads.filter(context_type='buy').first()
    assert thread is not None
    assert persona.name_in(thread, seller) == 'Сладости Самарканда'
    m = persona.mask(thread, seller)
    assert m['user_id'] is None and m['link'] == ''
    row = client.get('/api/v1/chat/', **auth(buyer)).json()['items'][0]
    assert row['title'] == 'Сладости Самарканда' and row['other_id'] is None
    # страница чата: ни ссылки на основной профиль, ни номера аккаунта продавца (жалоба и сделка идут по номеру чата)
    page = client.get(f'/chat/{thread.pk}/').content.decode()
    assert 'Сладости Самарканда' in page and f'/accounts/u/{seller.pk}/' not in page and f'to={seller.pk}' not in page
    assert 'name="who" value="thread"' in page and f'name="id" value="{seller.pk}"' not in page
    r = client.post('/report/', {'who': 'thread', 'thread': thread.pk, 'reason': 'spam', 'next': '/'})
    assert r.status_code == 302 and seller.pk in set(Report.objects.values_list('object_id', flat=True))
    # API объявления: автор без id; в ленте — тоже
    owner = client.get(f'/api/v1/pubs/buy/{item.pk}/', **auth(buyer)).json()['owner']
    assert owner == {'id': None, 'name': 'Сладости Самарканда'}
    # в обычном (не по объявлению) чате маски нет
    plain = services.open_direct(buyer, seller)
    assert persona.mask(plain, seller) is None
    # оставил ссылку на основной профиль — имя маски, но профиль открыт
    people.save_persona(seller, people.BOARD, 'Сладости Самарканда', link_main=True)
    assert people.face(seller)['id'] == seller.pk and persona.mask(thread, seller)['user_id'] == seller.pk
    # пустое имя — маска убрана
    people.save_persona(seller, people.BOARD, '')
    assert not people.face(seller)['masked'] and persona.mask(thread, seller) is None
    with pytest.raises(people.PeopleError):
        people.save_persona(seller, people.BOARD, 'Поддержка ilm4')                          # нельзя выдать себя за сотрудника


def test_spaces_persona_and_api(client, trio):
    a, b, _c = trio
    s = spaces.create(a, 'Клуб', '', is_public=True)
    spaces.join(s, b)
    general = s.threads.filter(kind='group').first()
    assert persona.name_in(general, b) == 'Биляль'
    r = client.post('/api/v1/me/personas/', {'section': 'spaces', 'name': 'CyberWolf'}, **auth(b))
    assert r.status_code == 200 and r.json()['items']['spaces']['name'] == 'CyberWolf'
    assert persona.name_in(general, b) == 'CyberWolf'                                       # общий профиль для сообществ
    spaces.set_nick(s, b, 'Волк')
    assert persona.name_in(general, b) == 'Волк'                                            # ник в сообществе важнее
    page = client.get('/accounts/personas/')
    assert page.status_code == 302                                                          # только для вошедших
    client.force_login(b)
    assert 'CyberWolf' in client.get('/accounts/personas/').content.decode()


def test_private_profile_requests(client, trio):
    a, b, c = trio
    post = social.create_post(a, 'Только для своих')
    social.follow(c, a)                                                                     # профиль ещё открыт — обычная подписка
    assert social.follow_state(c, a) == 'on'
    social.set_private(a, True)
    assert post in social.visible_posts(c) and post not in social.visible_posts(b) and post not in social.visible_posts(None)
    assert social.wall(a, b) == [] and not social.can_see_wall(a, b)
    social.follow(b, a)
    assert social.follow_state(b, a) == 'requested' and not social.is_following(b, a)
    assert social.counts(a, a)['followers'] == 1                                            # заявка не считается подписчиком
    assert a.notifications.filter(url='/feed/requests/').exists()
    assert [u.pk for u in social.follow_requests(a)] == [b.pk]
    # API: заявка видна автору, одобрение открывает стену
    r = client.get('/api/v1/feed/requests/', **auth(a)).json()
    assert [x['id'] for x in r['items']] == [b.pk]
    wall = client.get(f'/api/v1/feed/wall/{a.pk}/', **auth(b)).json()
    assert wall['locked'] and wall['requested'] and wall['items'] == []
    client.post('/api/v1/feed/requests/', {'user': b.pk, 'ok': '1'}, **auth(a))
    assert social.is_following(b, a) and post in social.visible_posts(b)
    # снова открыл профиль — ждавшие заявки становятся подписками
    social.follow(b, a, False)
    social.follow(b, a)
    assert social.follow_state(b, a) == 'requested'
    r = client.patch('/api/v1/me/', {'is_private': False}, content_type='application/json', **auth(a))
    assert r.status_code == 200 and r.json()['privacy']['private'] is False
    assert social.follow_state(b, a) == 'on'


def test_contact_alias_in_chats(client, trio):
    a, b, _c = trio
    thread = services.open_direct(a, b)
    services.send_text(thread, b, 'салам')
    people.add_contact(a, person=b, first_name='Брат Биляль')
    assert people.shown_name(b, a) == 'Брат Биляль' and people.shown_name(b, b) == 'Биляль'
    row = client.get('/api/v1/chat/', **auth(a)).json()['items'][0]
    assert row['title'] == 'Брат Биляль'
    client.force_login(a)
    assert 'Брат Биляль' in client.get(f'/chat/{thread.pk}/').content.decode()
    people.remove_contact(a, b)
    assert people.shown_name(b, a) == 'Биляль'


def test_search_home_and_space_sections(client, trio):
    a, b, _c = trio
    listing(a)
    s = spaces.create(a, 'Айтишники', '', is_public=True)
    # общий поиск: объявление и сообщество — в одном ответе
    html = client.get('/search/?q=финики').content.decode()
    assert 'Финики аджва' in html
    assert 'Айтишники' in client.get('/search/?q=айтишники').content.decode()
    # главная: гостю — что это за приложение, вошедшему — «что вас ждёт»
    guest = client.get('/?view=brief').content.decode()
    assert 'Что есть в ilm4' in guest and 'Создать аккаунт' in guest
    client.force_login(a)
    home = client.get('/?home=1&view=brief').content.decode()
    assert 'Вот что ждёт вас сейчас' in home and 'side__nav' in home
    # настройки сообщества по разделам: владельцу — роли, участнику без прав — только обзор
    assert 'Новая роль' in client.get(f'/communities/{s.pk}/?s=roles').content.decode()
    r = client.post(f'/communities/{s.pk}/act/', {'action': 'role_save', 'name': 'Учитель', 'color': '#22c55e'})
    assert r.status_code == 302 and r.url.endswith('?s=roles')
    spaces.join(s, b)
    client.force_login(b)
    page = client.get(f'/communities/{s.pk}/?s=roles').content.decode()
    assert 'Новая роль' not in page and 'Мой ник здесь' in page
    # API: данные для экрана управления — только тому, у кого есть права
    assert client.get(f'/api/v1/communities/{s.pk}/', **auth(b)).json()['manage'] is None
    manage = client.get(f'/api/v1/communities/{s.pk}/', **auth(a)).json()['manage']
    assert {'perm_choices', 'channels', 'invites', 'logs', 'banned'} <= set(manage)
    # API главной: что ждёт человека
    data = client.get('/api/v1/home/', **auth(a)).json()
    assert data['chats_unread'] == 0 and 'tracker' in data


def test_owner_stats_page(client, trio):
    a = trio[0]
    a.is_staff = True
    a.save()
    from apps.metrics import services as metrics
    metrics.record(a, '', 'chat', 60, 1)
    s = metrics.summary(30)
    assert s['funnel'][0]['n'] >= 3 and s['sleeping']['n'] == 0 and 'messages' in s['content'] and s['stickiness'] == 100
    client.force_login(a)


# ---------- v53 ----------

def test_recent_and_top_in_chat_search(client, trio):
    from apps.chat import finder
    a, b, c = trio
    t = services.open_direct(a, b)
    for _ in range(3):
        services.send_text(t, a, 'привет')
    services.send_text(services.open_direct(a, c), a, 'салам')
    assert [o.pk for _t, o in finder.top_people(a)] == [b.pk, c.pk]              # кому пишу чаще — тот первый
    finder.remember(a, 'u', c.pk)
    finder.remember(a, 't', t.pk)
    finder.remember(a, 'u', c.pk)                                               # повтор поднимает наверх, а не дублирует
    assert [(k, o.pk) for k, o in finder.recent(a)] == [('u', c.pk), ('t', t.pk)]
    client.force_login(a)
    data = client.get('/chat/find/').json()
    assert [x['name'] for x in data['top']] == ['Биляль', 'Умар'] and [x['kind'] for x in data['recent']] == ['u', 't']
    client.post('/chat/find/', {'kind': 's', 'id': 999})                           # несуществующее просто не покажется
    assert len(client.get('/chat/find/').json()['recent']) == 2
    api_data = client.get('/api/v1/chat/find/', **auth(a)).json()
    assert len(api_data['top']) == 2 and api_data['recent'][0]['kind'] == 'u'
    client.post('/chat/find/', {'clear': '1'})
    assert client.get('/chat/find/').json()['recent'] == []


def test_links_view_and_show(client, trio):
    a = trio[0]
    people.set_links(a, [{'kind': 'instagram', 'value': 'ali.dev'}, {'kind': 'website', 'value': 'https://ali.dev/'}])
    rows = people.links_for(a, a)
    assert [r['show'] for r in rows] == ['@ali.dev', 'ali.dev'] and people.links_view(a, len(rows)) == 'list'
    people.set_links(a, [{'kind': k, 'value': 'ali'} for k in ('instagram', 'telegram', 'github')])
    assert people.links_view(a, 3) == 'pills'                                   # «авто»: больше двух — пилюлями
    people.set_links(a, [{'kind': k, 'value': 'ali'} for k in ('instagram', 'telegram', 'github', 'youtube', 'tiktok', 'vk')])
    client.force_login(a)
    html = client.get(f'/accounts/u/{a.pk}/').content.decode()
    assert html.count('class="tp__pill tp__soc--') == 4 and 'ещё 2' in html and 'data-links-all' in html   # четыре видны, остальные — за «ещё»
    people.set_links(a, [{'kind': k, 'value': 'ali'} for k in ('instagram', 'telegram', 'github')])
    people.set_links_view(a, 'list')
    a.refresh_from_db()
    assert people.links_view(a, 3) == 'list'
    client.force_login(a)
    html = client.get(f'/accounts/u/{a.pk}/').content.decode()
    assert '@ali' in html and 'tp__brand' in html
    people.set_links_view(a, 'icons')
    assert 'tp__socs' in client.get(f'/accounts/u/{a.pk}/').content.decode()


def test_showcase_home_and_arrange(client, trio):
    from apps.core import showcase
    a = trio[0]
    listing(a)
    guest = client.get('/').content.decode()
    assert 'id="showcase"' in guest and 'Финики аджва' in guest                  # витрина по умолчанию: сервис показывает своё
    assert 'Вот что ждёт вас сейчас' not in client.get('/?view=brief').content.decode() and client.cookies['ilm4_home'].value == 'brief'
    client.force_login(a)
    assert 'Вот что ждёт вас сейчас' in client.get('/?home=1&view=brief').content.decode()
    a.refresh_from_db()
    assert a.ui['home_view'] == 'brief'
    client.get('/?home=1&view=showcase')
    keys = [w['key'] for w in showcase.widgets(a)['items']]
    assert keys[:2] == ['chat', 'buy'] or 'buy' in keys
    client.post('/home/widgets/', {'key': 'buy', 'action': 'hide'})
    a.refresh_from_db()
    data = showcase.widgets(a)
    assert 'buy' not in [w['key'] for w in data['items']] and [h['key'] for h in data['hidden']] == ['buy']
    client.post('/home/widgets/', {'key': 'buy', 'action': 'show'})
    client.post('/home/widgets/', {'key': 'buy', 'action': 'up'})
    a.refresh_from_db()
    after = [w['key'] for w in showcase.widgets(a)['items']]
    assert after.index('buy') == max(0, keys.index('buy') - 1)
    api_items = client.get('/api/v1/home/showcase/', **auth(a)).json()['items']
    assert [w['key'] for w in api_items] == after and api_items[after.index('buy')]['items'][0]['title'] == 'Финики аджва'


def test_ads_only_in_public_places(client, trio):
    from django.core.cache import cache

    from apps.chat import rooms
    from apps.chat.models import Thread
    from apps.core import ads
    from apps.core.models import Ad
    a, b, _c = trio
    ad = Ad.objects.create(title='Халяль-кафе «Зайнаб»', text='Плов и самса каждый день', url='/map/')
    cache.delete('ads:active')
    channel = rooms.create(a, Thread.CHANNEL, 'Новости города', is_public=True, handle='city_news_v53')
    group = rooms.create(a, Thread.GROUP, 'Соседи')
    direct = services.open_direct(a, b)
    assert ads.for_thread(channel)['title'] == ad.title
    assert ads.for_thread(group) is None and ads.for_thread(direct) is None        # в личных чатах и группах рекламы нет
    client.force_login(a)
    assert 'Реклама' in client.get(f'/chat/{channel.pk}/').content.decode()
    assert 'adx' not in client.get(f'/chat/{direct.pk}/').content.decode()
    r = client.get(f'/ad/{ad.pk}/')
    ad.refresh_from_db()
    assert r.status_code == 302 and r.url == '/map/' and ad.clicks == 1 and ad.impressions >= 2
    ad.is_active = False
    ad.save()
    cache.delete('ads:active')
    assert ads.pick('feed') is None and client.get(f'/ad/{ad.pk}/').status_code == 404


def test_call_support_into_listing_chat(client, trio):
    from apps.core.models import SiteSettings
    seller, buyer, staff = trio
    st = SiteSettings.get_solo()
    st.support_user = staff
    st.save()
    item = listing(seller)
    thread = services.open_direct(buyer, seller, 'Финики', context=('buy', item.pk))
    services.send_text(thread, buyer, 'секретная цена 100')
    personal = services.open_direct(buyer, seller)
    assert services.support_state(thread, buyer) == 'call' and services.support_state(personal, buyer) == ''
    with pytest.raises(services.ChatError):
        services.call_support(personal, buyer)                                   # в личный чат поддержку не зовут
    services.call_support(thread, buyer)
    assert services.support_state(thread, seller) == 'drop' and services.can_read(thread, staff)
    assert thread.other_participant(buyer) == seller                             # собеседник прежний, поддержка — третья
    services.send_text(thread, seller, 'после приглашения')
    seen = [m.body for m in services.visible_messages(thread, staff) if m.kind != 'system']
    assert seen == ['после приглашения']                                         # прошлую переписку поддержка не видит
    assert staff.notifications.filter(url=f'/chat/{thread.pk}/').exists()
    services.send_text(thread, staff, 'Чем помочь?')
    services.drop_support(thread, seller)
    assert not services.can_read(thread, staff) and services.support_state(thread, buyer) == 'call'


def test_no_calls_in_saved_messages(trio):
    a = trio[0]
    from apps.chat.models import Thread
    saved = Thread.objects.create(kind=Thread.DIRECT, context_type='saved')      # «Избранное» — чат с самим собой
    saved.participants.add(a)
    assert saved.is_saved and services.flags(saved)['calls'] is False and services.flags(saved)['video_calls'] is False
