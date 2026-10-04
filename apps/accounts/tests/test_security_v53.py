"""v53: двухшаговая защита для всех желающих, вход по QR-коду, активные сеансы."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts import devices, twofa
from apps.accounts.models import DeviceSession
from apps.api.models import ApiToken

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def ali():
    return User.objects.create_user('sec1', 'sec1@x.com', 'pass-12345', first_name='Али')


def code_of(device) -> str:
    return str(totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits)).zfill(6)


def test_twofa_for_ordinary_user(client, ali):
    client.post('/accounts/login/', {'login': 'sec1@x.com', 'password': 'pass-12345'})
    assert client.get('/accounts/profile/').status_code == 200                     # защита не включена — вход как раньше
    # подключение: страница с QR и ключом, подтверждение кодом
    page = client.get('/accounts/2fa/').content.decode()
    assert 'data:image/png;base64' in page
    device = TOTPDevice.objects.get(user=ali, confirmed=False)
    assert client.post('/accounts/2fa/', {'code': code_of(device)}).status_code == 302
    assert twofa.enabled(ali) and client.get('/accounts/profile/').status_code == 200   # этот браузер уже подтверждён
    # новый браузер: пароль верный, но дальше страницы кода не пускает
    other = Client()
    other.post('/accounts/login/', {'login': 'sec1@x.com', 'password': 'pass-12345'})
    r = other.get('/accounts/profile/')
    assert r.status_code == 302 and r.url == '/accounts/2fa/verify/'
    assert other.get('/chat/').status_code == 302
    assert other.post('/accounts/2fa/verify/', {'code': '000000'}).status_code == 200    # неверный код
    assert other.get('/accounts/profile/').status_code == 302
    # приложение: без кода токен не выдаётся
    r = other.post('/api/v1/auth/login/', {'login': 'sec1@x.com', 'password': 'pass-12345'}, content_type='application/json')
    assert r.status_code == 400 and r.json()['code'] == 'otp_required' and not ApiToken.objects.filter(user=ali).exists()
    r = other.post('/api/v1/auth/login/', {'login': 'sec1@x.com', 'password': 'pass-12345', 'otp': '123456'}, content_type='application/json')
    assert r.status_code == 400 and r.json()['code'] == 'otp_invalid'
    # WebSocket такой сессии — как гость
    assert twofa.session_locked(ali, other.session) and not twofa.session_locked(ali, client.session)


def test_twofa_verify_and_disable(client, ali):
    device = TOTPDevice.objects.create(user=ali, name='Основной', confirmed=True)
    twofa.forget(ali)
    client.post('/accounts/login/', {'login': 'sec1@x.com', 'password': 'pass-12345'})
    assert client.get('/').status_code == 302
    r = client.post('/accounts/2fa/verify/', {'code': code_of(device), 'next': '/chat/'})
    assert r.status_code == 302 and r.url == '/chat/'
    assert client.get('/accounts/profile/').status_code == 200
    # отключение — только с кодом (тот же код второй раз не принимается: защита от повтора)
    assert client.post('/accounts/2fa/', {'action': 'disable', 'code': '111111'}).status_code == 200
    assert twofa.enabled(ali)
    device.refresh_from_db()
    device.last_t = -1                      # следующий «шаг времени» — новый код
    device.throttling_failure_count, device.throttling_failure_timestamp = 0, None      # пауза после неверного кода прошла
    device.save()
    assert client.post('/accounts/2fa/', {'action': 'disable', 'code': code_of(device)}).status_code == 302
    assert not twofa.enabled(ali) and not ali.totpdevice_set.exists()


def test_twofa_code_tries_are_limited(ali):
    TOTPDevice.objects.create(user=ali, name='Основной', confirmed=True)
    for _ in range(twofa.TRIES):
        assert twofa.check(ali, '000001') is None
    assert twofa.blocked(ali)


def test_qr_login(client, ali):
    pc, phone = Client(), client
    phone.force_login(ali)
    r = pc.post('/accounts/qr/new/')
    assert r.status_code == 200 and r.json()['img'].startswith('data:image/png;base64')
    token = pc.session['qr']
    assert pc.get('/accounts/qr/status/').json() == {'state': 'wait'}
    # чужой браузер этот вход забрать не может — код привязан к тому, кто его показал
    thief = Client()
    assert thief.get('/accounts/qr/status/').json() == {'state': 'expired'}
    # телефон: видит, что за устройство, и подтверждает
    page = phone.get(f'/accounts/qr/{token}/').content.decode()
    assert 'Войти на новом устройстве?' in page
    assert phone.post(f'/accounts/qr/{token}/', {'ok': '1'}).status_code == 200
    assert thief.get('/accounts/qr/status/').json() == {'state': 'expired'}
    r = pc.get('/accounts/qr/status/').json()
    assert r['state'] == 'ok' and pc.get('/accounts/profile/').status_code == 200
    # код одноразовый
    assert pc.get('/accounts/qr/status/').json() == {'state': 'expired'}
    assert 'Код устарел' in phone.get(f'/accounts/qr/{token}/').content.decode()
    # отмена на телефоне — входа нет
    pc2 = Client()
    pc2.post('/accounts/qr/new/')
    phone.post(f"/accounts/qr/{pc2.session['qr']}/", {'ok': '0'})
    assert pc2.get('/accounts/qr/status/').json() == {'state': 'wait'}
    # подтверждение из приложения
    pc3 = Client()
    pc3.post('/accounts/qr/new/')
    auth = {'HTTP_AUTHORIZATION': f'Bearer {ApiToken.issue(ali, "android")}'}
    info = phone.get(f"/api/v1/auth/qr/{pc3.session['qr']}/", **auth).json()
    assert 'device' in info
    assert phone.post(f"/api/v1/auth/qr/{pc3.session['qr']}/", {}, content_type='application/json', **auth).json() == {'ok': True}
    assert pc3.get('/accounts/qr/status/').json()['state'] == 'ok'


def test_qr_login_does_not_bypass_twofa(client, ali):
    TOTPDevice.objects.create(user=ali, name='Основной', confirmed=True)
    twofa.forget(ali)
    pc = Client()
    pc.post('/accounts/qr/new/')
    assert devices.qr_approve(pc.session['qr'], ali)
    assert pc.get('/accounts/qr/status/').json()['state'] == 'ok'
    r = pc.get('/accounts/profile/')
    assert r.status_code == 302 and r.url == '/accounts/2fa/verify/'


def test_active_sessions(client, ali):
    a, b = client, Client()
    a.post('/accounts/login/', {'login': 'sec1@x.com', 'password': 'pass-12345'}, HTTP_USER_AGENT='Mozilla/5.0 (Windows NT 10.0) Chrome/126.0 Safari/537.36')
    b.post('/accounts/login/', {'login': 'sec1@x.com', 'password': 'pass-12345'}, HTTP_USER_AGENT='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Version/17.0 Mobile Safari/604.1')
    ApiToken.issue(ali, 'android')
    assert DeviceSession.objects.filter(user=ali).count() == 2
    rows = devices.sessions(ali, a.session.session_key)
    assert [r['current'] for r in rows] == [True, False, False] and rows[0]['title'] == 'Chrome · Windows'
    assert {r['title'] for r in rows} == {'Chrome · Windows', 'Safari · iPhone', 'ilm4 · Android'}
    page = a.get('/accounts/devices/').content.decode()
    assert 'Safari · iPhone' in page and 'Завершить все другие сеансы' in page
    # завершить один сеанс: второй браузер больше не в аккаунте
    other = next(r for r in rows if r['title'] == 'Safari · iPhone')
    a.post('/accounts/devices/', {'kind': 'web', 'id': other['id']})
    assert b.get('/accounts/profile/').status_code == 302 and a.get('/accounts/profile/').status_code == 200
    # завершить все остальные: приложение тоже выходит, текущий браузер остаётся
    a.post('/accounts/devices/', {'others': '1'})
    assert not ApiToken.objects.filter(user=ali).exists() and DeviceSession.objects.filter(user=ali).count() == 1
    assert a.get('/accounts/profile/').status_code == 200
    # выход убирает строку
    a.post('/accounts/logout/')
    assert not DeviceSession.objects.filter(user=ali).exists()
    # приложение: список и завершение сеанса сайта
    b.post('/accounts/login/', {'login': 'sec1@x.com', 'password': 'pass-12345'})
    auth = {'HTTP_AUTHORIZATION': f'Bearer {ApiToken.issue(ali, "android")}'}
    items = a.get('/api/v1/auth/sessions/', **auth).json()['items']
    assert [x['current'] for x in items] == [True, False]
    web = next(x for x in items if x['kind'] == 'web')
    left = a.post('/api/v1/auth/sessions/', {'kind': 'web', 'id': web['id']}, content_type='application/json', **auth).json()['items']
    assert len(left) == 1 and b.get('/accounts/profile/').status_code == 302
