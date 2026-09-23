"""v31: каталог сервисов, руководства, вход через Google (без ключей), беженцы по регионам."""
import pytest

from apps.refugee.models import Org

pytestmark = pytest.mark.django_db


def test_catalog_lists_groups(client):
    html = client.get('/catalog/').content.decode()
    assert 'Все сервисы' in html and 'Вера и знания' in html


def test_guides_available(client):
    assert 'шахада' in client.get('/islam/').content.decode().lower()
    assert 'Фатиха' in client.get('/salah/').content.decode()


def test_google_start_without_keys_redirects_to_login(client, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = ''
    settings.GOOGLE_OAUTH_CLIENT_SECRET = ''
    r = client.get('/accounts/google/')
    assert r.status_code == 302 and '/accounts/login/' in r['Location']


def test_google_start_with_keys_goes_to_google(client, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = 'cid'
    settings.GOOGLE_OAUTH_CLIENT_SECRET = 'sec'
    r = client.get('/accounts/google/')
    assert r.status_code == 302 and r['Location'].startswith('https://accounts.google.com/')
    assert 'state=' in r['Location']


def test_google_callback_rejects_bad_state(client, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = 'cid'
    settings.GOOGLE_OAUTH_CLIENT_SECRET = 'sec'
    r = client.get('/accounts/google/callback/', {'code': 'x', 'state': 'forged'})
    assert r.status_code == 302 and '/accounts/login/' in r['Location']


def test_refugee_region_autofill_and_tabs(client):
    o = Org.objects.create(country='Германия', name='Тест DE', kind='ngo')
    assert o.region == 'europe'
    html = client.get('/refugee/', {'tab': 'europe'}).content.decode()
    assert 'Тест DE' in html
    assert client.get('/refugee/', {'tab': 'lawyer'}).status_code == 200
