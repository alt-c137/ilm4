"""Раздел «Перевозки»: маршруты, модерация, фильтры."""
import pytest
from django.contrib.auth import get_user_model

from apps.core.models import Moderation
from apps.transport.models import Ride

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.get_or_create(username='demo', defaults={'email': 'd@x.com'})[0]


def make_ride(user, **kw):
    data = {'from_city': 'Хива', 'to_city': 'Самарканд', 'type': 'cargo',
            'price_text': '1 500 000 сум', 'description': 'Газель 3 т',
            'contact': '+998 90 000 00 00', 'owner': user,
            'status': Moderation.APPROVED}
    data.update(kw)
    return Ride.objects.create(**data)


def test_pending_hidden(client, user):
    make_ride(user, status=Moderation.PENDING)
    html = client.get('/transport/').content.decode()
    assert 'Хива' not in html


def test_list_route_cards(client, user):
    make_ride(user)
    html = client.get('/transport/').content.decode()
    assert 'Ташкент' in html and 'Москва' in html
    assert 'ГРУЗОПЕРЕВОЗКА' in html.upper()


def test_filters(client, user):
    make_ride(user)
    make_ride(user, from_city='Бухара', to_city='Дубай', type='pax',
              status=Moderation.APPROVED)
    html = client.get('/transport/', {'type': 'pax'}).content.decode()
    assert 'Дубай' in html and 'Хива' not in html
    html = client.get('/transport/', {'from': 'Хива'}).content.decode()
    assert 'Самарканд' in html and 'Дубай' not in html


def test_create_requires_login(client):
    assert client.get('/transport/add/').status_code == 302


def test_create_pending_and_moderation(client, user):
    client.force_login(user)
    client.post('/transport/add/', {
        'type': 'cargo', 'from_city': 'Бухара', 'to_city': 'Дубай',
        'price_text': 'договорная', 'description': 'Джумбо 10 т',
        'contact': '+998 90 111 11 11',
    })
    ride = Ride.objects.get(from_city='Бухара')
    assert ride.status == Moderation.PENDING
    assert ride.owner == user
