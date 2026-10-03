"""Поведение «как в Telegram» по фактам: галочки в группе, размеры фото, единый поиск, контакты, стартовый экран."""
import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.accounts import people
from apps.chat import finder, rooms, services
from apps.chat.events import decorate, message_payload
from apps.chat.models import Member, Message, Thread

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def trio():
    return [User.objects.create_user(f'tf{i}', f'tf{i}@x.com', 'x', first_name=n, handle=h, phone=f'+99890555000{i}', phone_verified_at=timezone.now())
            for i, (n, h) in enumerate([('Али', 'ali_dev'), ('Биляль', 'bilal_x'), ('Умар', 'umar_k')])]


def jpeg(w, h):
    buf = io.BytesIO()
    Image.new('RGB', (w, h), '#3366cc').save(buf, 'JPEG')
    return SimpleUploadedFile('p.jpg', buf.getvalue(), content_type='image/jpeg')


def test_group_ticks_like_telegram(trio):
    a, b, _c = trio
    g = rooms.create(a, Thread.GROUP, 'Семья')
    rooms.join(g, b, g.invite_code)
    m = services.send_text(g, a, 'Кто дома?')
    m = Message.objects.get(pk=m['id']) if isinstance(m, dict) else m
    m.thread = g
    decorate([m], a)
    assert message_payload(m)['read'] is False                      # ✓ — отправлено, никто не открыл
    Member.objects.filter(thread=g, user=b).update(last_read_at=timezone.now())
    decorate([m], a)
    assert message_payload(m)['read'] is True                       # ✓✓ — прочитал хотя бы один участник


def test_photo_keeps_its_proportions(trio):
    a, b, _c = trio
    t = services.open_direct(a, b)
    tall = services.store_upload(t, a, 'photo', jpeg(600, 1200))
    wide = services.store_upload(t, a, 'photo', jpeg(1600, 900))
    assert (tall['w'], tall['h']) == (600, 1200) and (wide['w'], wide['h']) == (1600, 900)   # клиент покажет вертикальное вертикальным


def test_one_search_finds_everything(trio, client):
    a, b, _c = trio
    t = services.open_direct(a, b)
    services.send_text(t, b, 'Встречаемся у мечети Минор в пять')
    ch = rooms.create(b, Thread.CHANNEL, 'Мечеть Минор — новости', is_public=True, handle='minor_news')
    out = finder.find(a, 'минор')                                   # регистр не важен, в том числе для кириллицы
    assert [r.pk for r in out['rooms']] == [ch.pk] and out['messages'][0]['thread'] == t.pk and 'Минор' in out['messages'][0]['text']
    assert [u.pk for u in finder.find(a, '@bilal')['people']] == [b.pk]
    services.clear_history(t, a)
    assert finder.find(a, 'Минор')['messages'] == []                # очищенная история в поиске не всплывает
    client.force_login(a)
    data = client.get('/chat/find/', {'q': 'Минор'}).json()
    assert data['global'][0]['name'] == 'Мечеть Минор — новости'


def test_contacts_like_telegram(trio, client):
    a, b, c = trio
    with pytest.raises(people.PeopleError):
        people.add_contact(a, '+998 90 000 00 00', first_name='Нет такого')
    people.add_contact(a, '+998 90 555 00 01', first_name='Брат', last_name='Биляль')
    people.add_contact(a, person=c)
    assert [name for _u, name in people.saved_contacts(a)] == ['Брат Биляль', 'Умар'] and people.is_contact(a, b)
    client.force_login(a)
    page = client.get('/chat/contacts/').content.decode()
    assert 'Брат Биляль' in page and 'Добавить контакт' in page and '555' not in page        # номер не показывается
    client.post('/chat/contacts/', {'remove': b.pk})
    assert not people.is_contact(a, b)


def test_start_screen_and_many_tabs(trio, client):
    from apps.core import tabs
    from apps.core.models import ModuleConfig
    a = trio[0]
    ModuleConfig.objects.update_or_create(key='chat', defaults={'name': 'Чат', 'status': 'on'})
    keys = ['home', 'chats', 'map', 'buy', 'news', 'jobs', 'forum', 'feed']
    assert tabs.clean_ui({'tabs_site': keys, 'start': 'chats'}) == {'tabs_site': keys, 'start': 'chats'}   # больше пяти — можно
    client.force_login(a)
    client.post('/settings/', {'what': 'tabs', 'tab': keys, 'start': 'chats'})
    a.refresh_from_db()
    assert a.ui['start'] == 'chats' and len(a.ui['tabs_site']) == 8
    assert client.get('/').url == '/chat/'                          # ilm4 открывается сразу как мессенджер
    assert client.get('/?home=1').status_code == 200                # главная никуда не делась
