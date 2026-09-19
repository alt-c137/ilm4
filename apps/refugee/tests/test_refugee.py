"""Раздел «Помощь беженцам»: справочник организаций с фильтрами."""
import pytest
from django.contrib.auth import get_user_model

from apps.refugee.models import Org

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def orgs():
    Org.objects.create(country='Турция', city='Анкара', name='УВКБ Турция',
                       kind='unhcr', phones='+90 312 000 00 00',
                       address='Ankara, Çankaya', website='https://www.unhcr.org/tr')
    Org.objects.create(country='Казахстан', city='Астана', name='УВКБ Казахстан',
                       kind='unhcr', website='https://help.unhcr.org/kazakhstan')


def test_list_shows_cards_and_phones(client, orgs):
    html = client.get('/refugee/').content.decode()
    assert 'УВКБ Турция' in html
    assert 'tel:+903120000000' in html          # кнопка звонка
    assert 'уточняйте' in html.lower()          # плашка актуальности


def test_country_filter(client, orgs):
    html = client.get('/refugee/', {'country': 'Казахстан'}).content.decode()
    assert 'УВКБ Казахстан' in html
    assert 'УВКБ Турция' not in html


def test_search(client, orgs):
    html = client.get('/refugee/', {'q': 'Анкара'}).content.decode()
    assert 'УВКБ Турция' in html
    html = client.get('/refugee/', {'q': 'Астана'}).content.decode()
    assert 'УВКБ Казахстан' in html and 'УВКБ Турция' not in html
