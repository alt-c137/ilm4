"""Свои нижние кнопки, оформление текста сообщений (жирный, скрытый…), имена «как в Telegram»."""
import json

import pytest
from django.contrib.auth import get_user_model

from apps.api.models import ApiToken
from apps.chat import richtext, rooms, services
from apps.core import tabs
from apps.core.models import ModuleConfig

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def ali(db, settings):
    settings.PUSH_DISABLED = True
    for key in ('chat', 'tracker', 'nikah', 'map', 'buy', 'prayer'):
        ModuleConfig.objects.update_or_create(key=key, defaults={'name': key, 'status': 'on'})
    return User.objects.create_user('ali', 'ali@x.com', 'x', first_name='Али')


def test_site_tabs_are_customizable(ali, client):
    client.force_login(ali)
    html = client.get('/').content.decode()
    assert html.index('href="/catalog/"') < html.index('tabbar__add')                    # обычный набор: Главная · Сервисы · Подать · Чаты
    r = client.post('/settings/', {'what': 'tabs', 'tab': ['chats', 'tracker', 'nikah', 'map']})
    assert r.status_code == 302
    ali.refresh_from_db()
    assert ali.ui == {'tabs_site': ['chats', 'tracker', 'nikah', 'map']}
    bar = client.get('/').content.decode().split('<nav class="tabbar"')[1].split('</nav>')[0]
    assert [bar.index(u) for u in ('/chat/', '/tracker/', '/nikah/', '/map/')] == sorted(bar.index(u) for u in ('/chat/', '/tracker/', '/nikah/', '/map/'))
    assert 'tabbar__add' not in bar and '/accounts/profile/' in bar                    # «Профиль» всегда на месте
    # выключенный в админке раздел из панели пропадает сам
    ModuleConfig.objects.filter(key='nikah').update(status='off')
    assert '/nikah/' not in client.get('/').content.decode().split('<nav class="tabbar"')[1].split('</nav>')[0]
    # мусор не сохраняется; «как было» — сброс
    client.post('/settings/', {'what': 'tabs', 'tab': ['hack', 'chats']})
    ali.refresh_from_db()
    assert 'tabs_site' not in ali.ui
    assert tabs.clean_ui({'tabs_site': ['home', 'home', 'x', 'chats', 'map', 'buy', 'news'], 'evil': 1}) == {'tabs_site': ['home', 'chats', 'map', 'buy']}


def test_app_tabs_saved_in_profile(ali, client):
    tok = ApiToken.issue(ali, 't')
    r = client.post('/api/v1/me/', json.dumps({'ui': {'tabs_app': ['home', 'tracker', 'chats', 'add', 'zzz']}}), content_type='application/json',
                    HTTP_AUTHORIZATION=f'Bearer {tok}')
    assert r.status_code == 200 and r.json()['ui'] == {'tabs_app': ['home', 'tracker', 'chats']}     # «Подать» в приложении нет


def test_rich_text_and_spoilers(ali):
    html = str(richtext.to_html('**Жирный** и __курсив__, ~~нет~~, `x**y`, ||секрет|| <script>alert(1)</script> https://ilm4.com/c/x.'))
    assert '<b>Жирный</b>' in html and '<i>курсив</i>' in html and '<s>нет</s>' in html and '<code>x**y</code>' in html
    assert '<span class="spoiler"' in html and '&lt;script&gt;' in html and '<script>' not in html
    assert '<a href="https://ilm4.com/c/x" target="_blank" rel="noopener nofollow ugc">https://ilm4.com/c/x</a>.' in html
    assert '"' not in str(richtext.to_html('https://a.b/"onmouseover="x')).split('</a>')[1]
    # скрытый текст не утекает в список чатов и уведомления
    assert richtext.plain('Пароль: ||1234|| и **важно**') == 'Пароль: ▒▒▒▒ и важно'
    umar = User.objects.create_user('umar', 'umar@x.com', 'x')
    t = services.open_direct(ali, umar)
    services.send_text(t, ali, 'Код ||9876||')
    from apps.core.models import Notification
    assert '9876' not in Notification.objects.get(user=umar).text
    rows = services.inbox(umar)
    from apps.chat.events import preview
    assert preview(rows[0][2]) == 'Код ▒▒▒▒'


def test_names_like_telegram(ali, client):
    ali.nickname = 'ali_nick'
    ali.save()
    assert ali.get_display_name() == 'Али'                                              # имя главнее старого «ника»
    ali.last_name = 'Каримов'
    assert ali.get_display_name() == 'Али Каримов'
    old = User.objects.create_user('old', 'old@x.com', 'x', nickname='Старый ник')
    assert old.get_display_name() == 'Старый ник'                                       # имени нет — показываем ник
    client.force_login(old)
    html = client.get('/accounts/profile/?edit=1').content.decode()
    assert 'value="Старый ник"' in html and 'Фамилия' in html                           # ник подставлен в «Имя»
    client.post('/accounts/profile/', {'first_name': 'Умар', 'last_name': 'Алиев', 'handle': '', 'bio': '', 'city': '', 'phone': ''})
    old.refresh_from_db()
    assert (old.first_name, old.last_name, old.nickname, old.get_display_name()) == ('Умар', 'Алиев', '', 'Умар Алиев')


def test_room_info_like_telegram(ali, client):
    ali.phone_verified_at = __import__('django.utils.timezone', fromlist=['now']).now()
    ali.save()
    g = rooms.create(ali, 'group', 'Соседи', 'О районе')
    client.force_login(ali)
    html = client.get(f'/chat/{g.pk}/info/').content.decode()
    assert 'tp__menu' in html and 'Удалить группу' in html and 'Ссылка-приглашение' in html and 'Сделать публичную ссылку' in html
    assert 'Удалить навсегда' not in html.split('tp__pop')[0]                           # опасная кнопка — только в меню «⋮»
    client.post(f'/chat/{g.pk}/info/', {'title': 'Соседи', 'about': '', 'is_public': 'on', 'handle': 'sosedi_1'})
    html = client.get(f'/chat/{g.pk}/info/').content.decode()
    assert '/c/sosedi_1/' in html and 'Публичная ссылка' in html and 'Ссылка-приглашение' in html
    assert 'Создать группу' in client.get('/chat/').content.decode()                    # меню «⋮» в списке чатов
