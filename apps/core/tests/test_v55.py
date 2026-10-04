"""v55: имя пользователя по правилам Telegram, меню аккаунтов, «дизайны» и «рабочие столы», свои элементы вместо браузерных."""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts import people
from apps.core import desks, tabs
from apps.core.models import ModuleConfig, SiteSettings

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def ali():
    for key, name in (('chat', 'Чат'), ('feed', 'Лента'), ('communities', 'Сообщества'), ('buy', 'Маркет'), ('jobs', 'Работа'),
                      ('news', 'Новости'), ('prayer', 'Намаз'), ('tracker', 'Трекер'), ('map', 'Карта')):
        ModuleConfig.objects.update_or_create(key=key, defaults={'name': name, 'status': 'on'})
    return User.objects.create_user('ali55', 'ali55@x.com', 'x', first_name='Али', phone='+998905551155', phone_verified_at=timezone.now())


def test_handle_rules_like_telegram(client, ali):
    """Латинские буквы, цифры и «_»; первая — буква; «_» не в конце и не подряд. Цифра и «_» НЕ обязательны; от 3 знаков."""
    assert people.clean_handle('isa', user=ali) == 'isa'                       # коротко и без цифр — можно
    assert people.clean_handle('@Ali_Dev', user=ali) == 'ali_dev'
    for bad, word in (('ab', 'коротк'), ('1ali', 'буквы'), ('_ali', 'буквы'), ('ali_', '«_»'), ('a__li', '«_»'), ('али', 'латинские'),
                      ('a' * 33, 'длинн')):
        with pytest.raises(people.PeopleError) as err:
            people.clean_handle(bad, user=ali)
        assert word in err.value.message, (bad, err.value.message)
    other = User.objects.create_user('o55', 'o55@x.com', 'x', handle='isa')
    assert people.handle_state('isa', user=ali) == {'ok': False, 'text': 'Это имя уже занято.'}
    assert people.handle_state('isa', user=other)['ok'] is True               # своё имя — «это ваше имя»
    assert people.handle_state('isa_2', user=ali) == {'ok': True, 'text': 'Имя @isa_2 свободно.'}
    client.force_login(ali)                                                    # проверка «на лету» — сайт и приложение
    assert client.get('/accounts/handle/check/?v=isa').json()['ok'] is False
    assert client.get('/accounts/handle/check/?v=muslim').json()['ok'] is True
    assert client.get('/accounts/handle/check/?v=support').json()['ok'] is False            # служебные имена — только команде
    from apps.api.models import ApiToken
    token = {'HTTP_AUTHORIZATION': f'Bearer {ApiToken.issue(ali, "t")}'}
    assert client.get('/api/v1/handle/check/?v=muslim', **token).json()['ok'] is True
    assert client.get('/api/v1/handle/check/?v=muslim&room=', **token).json()['ok'] is True   # адрес новой группы


def test_mention_of_short_handle():
    from apps.chat.richtext import to_html
    assert 'href="/@isa/"' in str(to_html('салам, @isa!'))


def test_menu_shows_tag_not_service_email(client):
    """Под именем — @имя или номер; служебный адрес входа через Telegram людям не показываем."""
    tg = User.objects.create_user('tg777', 'tg777@telegram.ilm4.local', 'x', first_name='Умар')
    assert tg.tag == ''
    tg.phone = '+998901112233'
    assert tg.tag == '+998901112233'
    tg.handle = 'umar'
    tg.save()
    assert tg.tag == '@umar'
    client.force_login(tg)
    html = client.get('/settings/').content.decode()
    assert 'telegram.ilm4.local' not in html and '@umar' in html and 'Добавить аккаунт' in html


def test_other_accounts_in_menu_switch_in_one_tap(client, ali):
    from apps.accounts import multi
    second = User.objects.create_user('second55', 'second55@x.com', 'x', first_name='Вторая')
    client.force_login(second)
    client.post('/accounts/accounts/', {'action': 'add'})                      # «Добавить аккаунт»: этот запомнен, вход во второй
    client.force_login(ali)
    html = client.get('/settings/').content.decode()
    assert 'umenu__acc' in html and 'Вторая' in html and multi.MAX == 5
    r = client.post('/accounts/accounts/switch/', {'user': second.pk})
    assert r.status_code == 302 and 'Вторая' in client.get('/settings/').content.decode().split('umenu__head')[1][:600]


def test_desks_and_designs(client, ali, settings):
    on = {'chat', 'feed', 'communities', 'buy', 'jobs', 'news', 'prayer', 'tracker', 'map'}
    assert desks.design_of(ali) == 'classic' and desks.desk_of(ali) == 'all'
    assert [t['key'] for t in tabs.site_tabs(ali, on, '/', True)] == ['home', 'services', 'add', 'chats']
    st = SiteSettings.get_solo()                                               # владелец задаёт, что видят новые люди
    st.default_design, st.default_desk = 'telegram', 'talk'
    st.save()
    assert desks.design_of(ali) == 'telegram' and desks.desk_of(ali) == 'talk'
    assert [t['key'] for t in tabs.site_tabs(ali, on, '/chat/', False)] == ['chats', 'communities', 'feed', 'services']
    assert tabs.start_url(ali, on) == '/chat/'
    client.force_login(ali)
    assert 'data-design="telegram"' in client.get('/settings/?s=look').content.decode()
    r = client.post('/settings/', {'what': 'look', 'design': 'avito', 'desk': 'market'})   # человек выбрал своё
    assert r.url == '/settings/?s=look'
    ali.refresh_from_db()
    assert ali.ui['design'] == 'avito' and ali.ui['desk'] == 'market' and ali.ui['tabs_site'] == ['home', 'buy', 'add', 'jobs', 'chats']
    assert tabs.start_url(ali, on) == '' and 'data-design="avito"' in client.get('/?home=1').content.decode()
    client.post('/settings/', {'what': 'tabs', 'tab': ['chats', 'map'], 'start': ''})     # подправил готовый набор
    ali.refresh_from_db()
    assert desks.desk_of(ali) == 'custom' and desks.design_of(ali) == 'avito'
    assert 'Свой' in client.get('/settings/?s=look').content.decode()


def test_welcome_screen_once(client, ali, settings):
    settings.WELCOME_SCREEN = True
    client.force_login(ali)
    assert client.get('/').url == '/welcome/'
    page = client.get('/welcome/').content.decode()
    assert 'Как Telegram' in page and 'Покупки и работа' in page and 'Пропустить' in page
    client.post('/settings/', {'what': 'look', 'design': 'insta', 'desk': 'social', 'next': '/'})
    ali.refresh_from_db()
    assert ali.ui['welcomed'] == 1 and ali.ui['start'] == 'feed'
    assert client.get('/').url == '/feed/'                                     # стол «Лента и люди» открывается с ленты
    skip = User.objects.create_user('skip55', 'skip55@x.com', 'x')
    client.force_login(skip)
    assert client.post('/welcome/').url == '/' and client.get('/').status_code == 200


def test_own_controls_are_loaded(client, ali):
    """Свои список, календарь и окно аватара подключены на каждой странице; системных полей даты в разметке групп нет."""
    client.force_login(ali)
    html = client.get('/settings/').content.decode()
    for part in ('css/tgui.css', 'js/select.js', 'js/datepick.js', 'js/avatarcrop.js'):
        assert part in html, part
    priv = client.get('/accounts/profile/?s=privacy').content.decode()
    assert priv.count('class="tgs__row"') >= 7 and 'type="checkbox"' in priv
    r = client.post('/accounts/profile/', {'s': 'privacy', 'first_name': 'Али', 'phone': ali.phone, 'phone_privacy': 'nobody', 'seen_privacy': 'all',
                                           'forward_privacy': 'all', 'invite_privacy': 'all', 'counts_privacy': 'all'}, HTTP_X_AUTOSAVE='1')
    assert r.json() == {'ok': True}                                            # переключил — сохранилось без перезагрузки
    ali.refresh_from_db()
    assert ali.phone_privacy == 'nobody'


def test_backup_codes_for_two_step(client, ali):
    """Запасные коды: выдаются по коду из приложения, каждый срабатывает один раз, в базе лежат только отпечатки."""
    from django_otp.oath import totp
    from django_otp.plugins.otp_totp.models import TOTPDevice

    from apps.accounts import twofa
    from apps.accounts.models import BackupCode
    device = TOTPDevice.objects.create(user=ali, name='Основной', confirmed=True)

    def now_code():
        TOTPDevice.objects.filter(pk=device.pk).update(last_t=-1, throttling_failure_count=0, throttling_failure_timestamp=None)
        return f'{totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits):06d}'
    client.force_login(ali)
    session = client.session
    session['otp_device_id'] = device.persistent_id
    session.save()
    assert 'Запасные коды' in client.get('/accounts/2fa/').content.decode()
    assert BackupCode.objects.count() == 0
    client.post('/accounts/2fa/', {'action': 'codes', 'code': '000000'})                     # неверный код — кодов не будет
    assert BackupCode.objects.count() == 0
    page = client.post('/accounts/2fa/', {'action': 'codes', 'code': now_code()}).content.decode()
    codes = __import__('re').findall(r'<code>([a-z0-9]{4}-[a-z0-9]{4})</code>', page)
    assert len(codes) == 10 and BackupCode.objects.filter(user=ali).count() == 10
    assert not BackupCode.objects.filter(code_hash__in=[c.replace('-', '') for c in codes]).exists()   # сами коды в базе не лежат
    assert twofa.backup_left(ali) == 10
    assert twofa.check(ali, codes[0].upper()) is not None and twofa.backup_left(ali) == 9     # сработал (регистр и дефис не важны)
    assert twofa.check(ali, codes[0]) is None                                                # второй раз — уже нет
    assert twofa.check(ali, 'zzzz-zzzz') is None
    other = User.objects.create_user('other55', 'other55@x.com', 'x')
    assert twofa.check(other, codes[1]) is None                                              # чужой код не подходит
    from apps.api.models import ApiToken  # noqa: F401 — вход приложения принимает запасной код так же
    r = client.post('/api/v1/auth/login/', {'login': 'ali55@x.com', 'password': 'x', 'otp': codes[2]}, content_type='application/json')
    assert r.status_code == 200 and r.json().get('token')
