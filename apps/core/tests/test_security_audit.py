"""Проверка безопасности (октябрь 2026): каждая закрытая дыра — тест, чтобы она не вернулась.

Что проверяется: чужой код через текст и имена в чате, права модератора сообщества, текст сообщений в уведомлениях,
флуд, «бомбы» из картинок, пачки аккаунтов, поиск человека по email, раздувание таблицы аналитики, старые входы."""
import io
import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings as dj_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.api.models import ApiToken
from apps.chat import richtext, rooms, services, spaces
from apps.chat.models import Member, SpaceMember, Thread
from apps.chat.rooms import ChatError
from apps.core.models import ModuleConfig, Notification

User = get_user_model()
pytestmark = pytest.mark.django_db
ROOT = Path(dj_settings.BASE_DIR)


@pytest.fixture
def trio():
    for key, name in (('chat', 'Чат'), ('communities', 'Сообщества')):
        ModuleConfig.objects.update_or_create(key=key, defaults={'name': name, 'status': 'on'})
    return [User.objects.create_user(f's{i}', f's{i}@x.com', 'x', first_name=n, phone=f'+99890555000{i}', phone_verified_at=timezone.now())
            for i, n in enumerate(['Али', 'Биляль', 'Умар'])]


# ---------- чужой код на странице (XSS) ----------

def test_link_cannot_break_out_of_attribute():
    """Кавычка в ссылке не закрывает href и не добавляет свой атрибут (onmouseover=…)."""
    for text in ('см https://x.com/" onmouseover="alert(1)', 'https://x.com/"onmouseover="alert(1)//x', "https://x.com/'onfocus='alert(1)"):
        html = str(richtext.to_html(text))
        assert 'onmouseover="' not in html and "onfocus='" not in html
        assert html.count('"') == html.count('href="') * 2 + html.count('target="_blank"') * 2 + html.count('rel="') * 2
    assert str(richtext.to_html('вот (https://a.uz/p?a=1&b=2).')) == \
        'вот (<a href="https://a.uz/p?a=1&amp;b=2" target="_blank" rel="noopener nofollow ugc">https://a.uz/p?a=1&amp;b=2</a>).'


def test_control_character_does_not_crash_rendering(client, trio):
    """Служебный знак разметки в тексте сообщения раньше ронял страницу чата у всех участников."""
    a, b, _c = trio
    assert '\x00' not in str(richtext.to_html('\x000\x00 и `код` \x007\x00'))
    t = services.open_direct(a, b)
    services.send_text(t, a, 'привет \x000\x00')
    client.force_login(b)
    assert client.get(f'/chat/{t.pk}/').status_code == 200


def test_js_escapes_quotes():
    """Имена и тексты попадают в атрибуты (data-name="…"): экранировать нужно и кавычки, не только < > &."""
    for name in ('chat.js', 'chatlist.js', 'voice.js', 'mapx.js'):
        src = (ROOT / 'static/js' / name).read_text()
        body = re.search(r'function esc\([a-z]\) \{[^\n]+', src).group(0)
        assert "ESC[c]" in body and 'innerHTML' not in body, name
        assert "'\"': '&quot;'" in src and '"\'": \'&#39;\'' in src, name


def test_no_inline_handlers_in_templates():
    """В разметке нет onclick="…": страницам запрещено исполнять код из атрибутов (см. заголовок ниже)."""
    bad = []
    for path in list(ROOT.glob('templates/**/*.html')) + list(ROOT.glob('apps/*/templates/**/*.html')):
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r'<[^>]*\son[a-z]+\s*=\s*["\']', line) or 'javascript:' in line:
                bad.append(f'{path.relative_to(ROOT)}:{i}')
    assert not bad, bad


def test_content_policy_header(client, trio):
    response = client.get('/accounts/login/')
    assert "script-src-attr 'none'" in response['Content-Security-Policy']
    assert 'data-confirm' not in response.content.decode()          # страница входа: подтверждений нет
    a, b, _c = trio
    t = services.open_direct(a, b)
    client.force_login(a)
    page = client.get(f'/chat/{t.pk}/')
    assert "script-src-attr 'none'" in page['Content-Security-Policy'] and 'data-confirm="' in page.content.decode()


# ---------- сообщества: модератор не обходит права ----------

def test_space_moderator_cannot_use_group_levers(client, trio):
    owner, mod, outsider = trio
    space = spaces.create(owner, 'Клуб', is_public=False)
    spaces.join(space, mod, space.invite_code)
    spaces.set_role(space, owner, mod, SpaceMember.MOD)                 # модератор: удалять сообщения — да, каналы — нет
    secret = spaces.add_channel(space, owner, 'правление', private=True)
    spaces.save_role(space, owner, None, 'Совет', '#3366ff', [], False)
    role = space.roles.get(name='Совет')
    spaces.set_channel(space, owner, secret.pk, title='правление', private=True, role_ids=[role.pk])
    spaces.set_member_roles(space, owner, mod, [role.pk])
    assert rooms.is_admin(secret, mod) and not spaces.can(space, mod, 'manage_channels')

    with pytest.raises(ChatError):                                       # открыть закрытый канал всем
        rooms.update(secret, mod, {'is_public': 'on', 'handle': 'leak_channel', 'title': 'x'})
    with pytest.raises(ChatError):
        rooms.reset_invite(secret, mod)
    services.open_direct(mod, outsider)
    with pytest.raises(ChatError):                                       # добавить постороннего мимо сообщества
        rooms.add_members(secret, mod, [outsider])
    with pytest.raises(ChatError):
        rooms.remove_member(secret, mod, owner)
    with pytest.raises(ChatError):                                       # и владелец — только через сообщество
        rooms.update(secret, owner, {'is_public': 'on', 'handle': 'leak_channel'})
    with pytest.raises(ChatError):
        rooms.delete(secret, owner)
    secret.refresh_from_db()
    assert not secret.is_public and not secret.handle and secret.title == 'правление'
    assert not secret.participants.filter(pk=outsider.pk).exists()

    client.force_login(mod)                                              # то же через страницу сайта и API
    client.post(f'/chat/{secret.pk}/info/', {'title': 'взлом', 'is_public': 'on', 'handle': 'leak_channel'})
    token = {'HTTP_AUTHORIZATION': f'Bearer {ApiToken.issue(mod, "t")}'}
    assert client.post(f'/api/v1/chat/{secret.pk}/room/', {'is_public': '1', 'handle': 'leak_channel'}, **token).status_code == 409
    secret.refresh_from_db()
    assert not secret.is_public and secret.title == 'правление'
    assert client.get(f'/chat/{secret.pk}/info/').url == f'/communities/{space.pk}/'
    spaces.delete_channel(space, owner, thread_id=secret.pk)             # в самом сообществе всё работает
    assert not Thread.objects.filter(pk=secret.pk).exists()


def test_room_action_returns_only_to_own_pages(client, trio):
    a, _b, _c = trio
    room = rooms.create(a, Thread.GROUP, 'Соседи')
    client.force_login(a)
    assert client.post(f'/chat/{room.pk}/room/mute/', {'next': 'https://evil.example/x'}).url == f'/chat/{room.pk}/'
    assert client.post(f'/chat/{room.pk}/room/unmute/', {'next': '/chat/'}).url == '/chat/'


# ---------- уведомления не хранят текст переписки ----------

def test_notification_keeps_no_message_text(trio, monkeypatch, django_capture_on_commit_callbacks):
    a, b, _c = trio
    sent = []
    monkeypatch.setattr('apps.api.push.send_to_user', lambda uid, body, url='', **kw: sent.append((uid, body)))
    t = services.open_direct(a, b)
    with django_capture_on_commit_callbacks(execute=True):
        services.send_text(t, a, 'пароль от сейфа 4711')          # отправка сама уведомляет получателя
    note = Notification.objects.get(user=b)
    assert '4711' not in note.text and note.text == 'Али: новое сообщение'
    assert sent == [(b.pk, 'Али: пароль от сейфа 4711')]               # сам текст — только в пуше на телефон
    with django_capture_on_commit_callbacks(execute=True):
        services.notify(t, a, 'второе письмо')
    assert Notification.objects.filter(user=b).count() == 1             # пока не прочитано — одна строка на чат
    assert sent[-1] == (b.pk, 'Али: второе письмо')
    Notification.objects.filter(user=b).update(read=True)
    services.notify(t, a, 'третье')
    assert Notification.objects.filter(user=b).count() == 2
    assert not Notification.objects.filter(text__contains='третье').exists()


def test_old_notification_previews_are_scrubbed(trio):
    import importlib

    from django.apps import apps as dj_apps
    a, _b, _c = trio
    old = Notification.objects.create(user=a, url='/chat/12/', text='Биляль: встретимся в 5 у метро')
    keep = Notification.objects.create(user=a, url='/my/', text='«Финики» одобрено: опубликовано.')
    importlib.import_module('apps.core.migrations.0043_scrub_chat_notes').scrub(dj_apps, None)
    old.refresh_from_db()
    keep.refresh_from_db()
    assert old.text == 'Биляль: новое сообщение' and keep.text == '«Финики» одобрено: опубликовано.'


# ---------- флуд, поиск, «бомбы» из картинок ----------

def test_flood_limit_counts_all_clients(client, trio):
    a, b, _c = trio
    t = services.open_direct(a, b)
    for i in range(services.FLOOD_MAX):
        services.send_text(t, a, f'сообщение {i}')
    with pytest.raises(ChatError) as err:
        services.send_text(t, a, 'ещё одно')
    assert err.value.status == 429
    token = {'HTTP_AUTHORIZATION': f'Bearer {ApiToken.issue(a, "t")}'}       # приложение — тот же счётчик
    assert client.post(f'/api/v1/chat/{t.pk}/send/', {'body': 'из приложения'}, content_type='application/json', **token).status_code == 429
    services.send_text(t, b, 'у собеседника свой счётчик')


def test_search_is_rate_limited(trio):
    from apps.chat import msgops
    a, b, _c = trio
    t = services.open_direct(a, b)
    services.send_text(t, a, 'ищи слово финики')
    assert len(msgops.search_messages(t, b, 'финики')) == 1
    from django.core.cache import cache
    cache.set(f'chat:search:{b.pk}', services.SEARCH_MAX, 60)
    assert msgops.search_messages(t, b, 'финики') == []


def test_huge_picture_is_refused(trio):
    """Маленький файл с огромными размерами в точках («бомба») отклоняется до раскрытия."""
    from PIL import Image
    a, b, _c = trio
    t = services.open_direct(a, b)
    buf = io.BytesIO()
    Image.new('1', (9000, 9000)).save(buf, 'PNG')                        # 81 Мп, а файл — несколько килобайт
    assert len(buf.getvalue()) < 200_000
    with pytest.raises(ChatError) as err:
        services.store_upload(t, a, 'photo', SimpleUploadedFile('bomb.png', buf.getvalue(), content_type='image/png'))
    assert 'Слишком большое' in err.value.message
    ok = io.BytesIO()
    Image.new('RGB', (4000, 3000), 'white').save(ok, 'JPEG')            # обычный снимок 12 Мп проходит
    payload = services.store_upload(t, a, 'photo', SimpleUploadedFile('ok.jpg', ok.getvalue(), content_type='image/jpeg'))
    assert payload['kind'] == 'photo' and max(payload['w'], payload['h']) <= 2048


# ---------- пачки аккаунтов и рассылки ----------

def test_registration_is_limited_per_address(client, settings):
    from apps.accounts.views import REG_PER_HOUR
    settings.CLIENT_IP_HEADER = 'HTTP_X_REAL_IP'                         # как на сервере: адрес сообщает nginx
    for i in range(REG_PER_HOUR):
        r = client.post('/accounts/register/', {'email': f'new{i}@x.com', 'password1': 'Str0ng-pass-77', 'password2': 'Str0ng-pass-77'},
                        HTTP_X_REAL_IP='203.0.113.9')
        assert r.status_code == 302, r.content.decode()[:300]
        client.post('/accounts/logout/')
    r = client.post('/accounts/register/', {'email': 'extra@x.com', 'password1': 'Str0ng-pass-77', 'password2': 'Str0ng-pass-77'},
                    HTTP_X_REAL_IP='203.0.113.9')
    assert r.status_code == 200 and not User.objects.filter(email='extra@x.com').exists()
    r = client.post('/accounts/register/', {'email': 'other@x.com', 'password1': 'Str0ng-pass-77', 'password2': 'Str0ng-pass-77'},
                    HTTP_X_REAL_IP='203.0.113.10')
    assert r.status_code == 302                                           # с другого адреса — можно


def test_new_dialogs_without_phone_are_few(settings):
    from apps.accounts import people
    fresh = User.objects.create_user('fresh', 'fresh@x.com', 'x')
    known = User.objects.create_user('known', 'known@x.com', 'x', phone='+998905550099', phone_verified_at=timezone.now())
    other = User.objects.create_user('other', 'other@x.com', 'x')
    for _i in range(people.NEW_CHATS_NO_PHONE + 3):                       # бот не подключён — подтвердить номер нечем: общий предел
        people.check_new_chat(fresh, other)
    settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_BOT_USERNAME = '1:T', 'ilm4_bot'
    from django.core.cache import cache
    cache.clear()
    for _i in range(people.NEW_CHATS_NO_PHONE):
        people.check_new_chat(fresh, other)
    with pytest.raises(people.PeopleError) as err:
        people.check_new_chat(fresh, other)
    assert err.value.status == 429 and 'номер' in err.value.message
    for _i in range(people.NEW_CHATS_NO_PHONE + 5):                       # с подтверждённым номером — прежние 30 в сутки
        people.check_new_chat(known, other)


# ---------- аналитика и старые входы ----------

def test_guest_analytics_rows_are_capped(client, settings):
    from apps.metrics import services as metrics
    from apps.metrics.models import Use
    ModuleConfig.objects.update_or_create(key='buy', defaults={'name': 'Маркет', 'status': 'on'})
    client.cookies['ilm4_v'] = '<script>alert(1)</script>'               # чужой формат куки не принимаем
    assert client.post('/m/', {'s': 'buy', 't': '10', 'o': '1'}).status_code == 204
    row = Use.objects.get()
    assert re.fullmatch(r'[0-9a-f]{16}', row.anon)
    for i in range(metrics.GUEST_ROWS_PER_HOUR + 20):                     # каждый запрос — с новой «кукой гостя»
        metrics.record(None, f'{i:016x}', 'buy', 5, 1, ip='198.51.100.7')
    assert Use.objects.filter(section='buy').count() == metrics.GUEST_ROWS_PER_HOUR + 1
    metrics.record(None, f'{3:016x}', 'buy', 5, 0, ip='198.51.100.7')     # уже известный гость считается дальше
    assert Use.objects.get(anon=f'{3:016x}').seconds == 10


def test_idle_app_login_expires(client):
    user = User.objects.create_user('idle', 'idle@x.com', 'x')
    raw = ApiToken.issue(user, 'старый телефон')
    assert ApiToken.lookup(raw) is not None
    ApiToken.objects.filter(user=user).update(last_used_at=timezone.now() - timedelta(days=ApiToken.IDLE_DAYS - 2))
    assert ApiToken.lookup(raw) is not None
    ApiToken.objects.filter(user=user).update(last_used_at=timezone.now() - timedelta(days=ApiToken.IDLE_DAYS + 1))
    assert ApiToken.lookup(raw) is None and not ApiToken.objects.filter(user=user).exists()
    assert client.get('/api/v1/me/', HTTP_AUTHORIZATION=f'Bearer {raw}').status_code == 401


def test_visitor_address_trusts_only_the_real_front(rf, settings):
    """Адрес посетителя берём только от того, кто действительно стоит перед сайтом; чужим заголовкам не верим."""
    from apps.core.limits import client_ip
    forged = {'HTTP_X_REAL_IP': '1.1.1.1', 'HTTP_CF_CONNECTING_IP': '2.2.2.2', 'HTTP_X_FORWARDED_FOR': '3.3.3.3'}
    assert client_ip(rf.get('/', REMOTE_ADDR='198.51.100.20', **forged)) == '198.51.100.20'     # прямое соединение
    # свой ПК с туннелем: запрос пришёл от туннеля на этом же компьютере — берём адрес, который он сообщил
    assert client_ip(rf.get('/', REMOTE_ADDR='127.0.0.1', HTTP_CF_CONNECTING_IP='203.0.113.7')) == '203.0.113.7'
    assert client_ip(rf.get('/', REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR='9.9.9.9, 203.0.113.8')) == '203.0.113.8'
    assert client_ip(rf.get('/', REMOTE_ADDR='127.0.0.1')) == '127.0.0.1'
    settings.CLIENT_IP_HEADER = 'HTTP_X_REAL_IP'                         # сервер: адрес кладёт nginx
    assert client_ip(rf.get('/', REMOTE_ADDR='172.18.0.5', HTTP_X_REAL_IP='203.0.113.5', HTTP_CF_CONNECTING_IP='2.2.2.2')) == '203.0.113.5'


def test_audit_log_keeps_visitor_address(rf, settings):
    from apps.accounts.audit import log_action
    from apps.accounts.models import AuditLog
    settings.CLIENT_IP_HEADER = 'HTTP_X_REAL_IP'
    request = rf.get('/', HTTP_X_REAL_IP='203.0.113.5', REMOTE_ADDR='172.18.0.5')   # 172.18… — адрес nginx в сети Docker
    request.user = User.objects.create_user('adm', 'adm@x.com', 'x', is_staff=True)
    log_action(request, 'проверка')
    assert AuditLog.objects.get().ip == '203.0.113.5'


def test_group_levers_still_work_for_ordinary_groups(trio):
    """Обычные группы и каналы (не из сообщества) настраиваются как раньше."""
    a, b, _c = trio
    room = rooms.create(a, Thread.CHANNEL, 'Новости махалли')
    rooms.update(room, a, {'is_public': 'on', 'handle': 'mahalla_news'})
    room.refresh_from_db()
    assert room.is_public and room.handle == 'mahalla_news'
    rooms.join(room, b)
    rooms.set_admin(room, a, b, True)
    assert Member.objects.get(thread=room, user=b).role == Member.ADMIN
    old = room.invite_code
    assert rooms.reset_invite(room, b) != old
    rooms.remove_member(room, a, b)
    rooms.delete(room, a)
