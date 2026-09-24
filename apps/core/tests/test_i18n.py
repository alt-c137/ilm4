"""Языки интерфейса (ru/uz/en) и капча."""
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _cache():
    cache.clear()
    yield
    cache.clear()


def test_english_and_uzbek_interface(client):
    client.cookies['django_language'] = 'en'
    html = client.get('/accounts/login/').content.decode()
    assert 'Forgot your password?' in html and 'lang="en"' in html
    client.cookies['django_language'] = 'uz'
    assert 'Parolni unutdingizmi?' in client.get('/accounts/login/').content.decode()


def test_switch_language_saves_to_profile(client):
    u = User.objects.create_user('l', 'l@x.com', 'x')
    client.force_login(u)
    resp = client.post('/lang/', {'language': 'uz', 'next': '/nikah/'})
    assert resp.url == '/nikah/' and resp.cookies['django_language'].value == 'uz'
    u.refresh_from_db()
    assert u.language == 'uz'
    # другое устройство без куки — язык из профиля
    from django.test import Client
    other = Client()
    other.force_login(u)
    resp = other.get('/accounts/login/')
    assert resp.cookies['django_language'].value == 'uz'
    assert 'Parolni unutdingizmi?' in resp.content.decode()


def test_bad_language_ignored(client):
    resp = client.post('/lang/', {'language': 'xx', 'next': 'https://evil.com/'})
    assert resp.url == '/' and 'django_language' not in resp.cookies


def test_notification_in_recipient_language():
    from apps.core.models import Notification
    from apps.nikah import services
    from apps.nikah.tests.test_nikah import make_profile
    b = make_profile('b@x.com', 'M')
    s = make_profile('s@x.com', 'F')
    s.user.language = 'en'
    s.user.save()
    services.send_interest(b, s)      # брат по-русски → сестре по-английски
    assert Notification.objects.get(user=s.user).text == 'Someone showed interest in your nikah profile'


def test_country_stored_canonical(client):
    from apps.nikah.models import NikahProfile
    from apps.nikah.tests.test_nikah import wizard_data
    u = User.objects.create_user('c', 'c@x.com', 'x')
    client.force_login(u)
    client.cookies['django_language'] = 'en'
    client.post('/nikah/create/', wizard_data(relocation='stay', country='Uzbekistan'))
    p = NikahProfile.objects.get(user=u)
    assert p.country == 'Узбекистан'


def test_captcha_required_when_enabled(client, settings, monkeypatch):
    settings.TURNSTILE_SITE_KEY, settings.TURNSTILE_SECRET_KEY = 'site', 'secret'
    calls = []

    class R:
        def __init__(self, ok):
            self.ok = ok

        def json(self):
            return {'success': self.ok}
    monkeypatch.setattr('apps.core.captcha.requests.post',
                        lambda *a, **k: calls.append(k['data']['response']) or R(k['data']['response'] == 'good'))
    data = {'email': 'n@x.com', 'password1': 'Str0ng-pass-1', 'password2': 'Str0ng-pass-1'}
    assert 'cf-turnstile' in client.get('/accounts/register/').content.decode()
    client.post('/accounts/register/', data)
    assert not User.objects.filter(email='n@x.com').exists()          # без капчи — нет
    client.post('/accounts/register/', {**data, 'cf-turnstile-response': 'good'})
    assert User.objects.filter(email='n@x.com').exists()
