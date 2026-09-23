"""Фаза 4 — карта и здоровье: модерация, фильтры, публикация, платный врач."""

import pytest
from django.contrib.auth import get_user_model

from apps.core.models import Moderation, SiteSettings
from apps.maps.models import HalalPlace
from apps.maps.services import distance_km, nearby
from apps.wallet import services as wallet
from apps.wallet.models import Transaction

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_place(name='Кафе Зайнаб', city='Ташкент', status=Moderation.APPROVED, **kw):
    return HalalPlace.objects.create(
        name=name, category='cafe', city=city, address='ул. Пример 1',
        lat=41.31, lon=69.28, status=status, **kw,
    )


def test_pending_place_hidden(client):
    make_place(status=Moderation.PENDING)
    response = client.get('/map/')
    assert 'Кафе Зайнаб' not in response.content.decode()

    make_place('Ресторан Халяль')  # одобренный виден
    assert 'Ресторан Халяль' in client.get('/map/').content.decode()


def test_map_markers_json(client):
    make_place()
    html = client.get('/map/').content.decode()
    assert 'Кафе Зайнаб' in html and 'circleMarker' in html  # карта и маркеры на месте


def test_map_filters(client):
    make_place('Кафе Один', city='Ташкент')
    make_place('Кафе Два', city='Казань')
    html = client.get('/map/', {'city': 'Казань'}).content.decode()
    assert 'Кафе Два' in html and 'Кафе Один' not in html


def test_add_place_requires_login(client):
    assert client.get('/map/add/').status_code == 302


def test_user_adds_place_pending(client):
    user = User.objects.create_user('u', 'u@x.com', 'x')
    client.force_login(user)
    client.post('/map/add/', {'pledge': '1', 
        'name': 'Магазин Бисмиллах', 'category': 'shop', 'city': 'Бухара',
        'lat': '39.77', 'lon': '64.46',
    })
    place = HalalPlace.objects.get(name='Магазин Бисмиллах')
    assert place.status == Moderation.PENDING  # сразу не публикуется
    assert place.owner == user


def test_distance_and_nearby():
    # Ташкент → Самарканд ≈ 270 км
    d = distance_km(41.3111, 69.2797, 39.6542, 66.9597)
    assert 250 < d < 300
    near = nearby([make_place()], 41.30, 69.27, radius_km=50)
    assert len(near) == 1 and near[0].distance_km < 5


def test_health_pages(client):
    response = client.get('/health/')
    assert response.status_code == 200


def test_doctor_publish_free(client):
    user = User.objects.create_user('d', 'd@x.com', 'x')
    client.force_login(user)
    client.post('/health/add/', {'pledge': '1', 
        'name': 'Доктор Ахмед', 'category': 'cardio', 'city': 'Казань',
        'experience': '10', 'lat': '55.79', 'lon': '49.10',
    })
    from apps.health.models import Doctor

    doctor = Doctor.objects.get(name='Доктор Ахмед')
    assert doctor.status == Moderation.PENDING
    assert wallet.balance_of(user) == 0  # бесплатно — ничего не списано


def test_doctor_publish_paid(client):
    settings_obj = SiteSettings.get_solo()
    settings_obj.doctor_publish_price = 50_000
    settings_obj.save()
    user = User.objects.create_user('d2', 'd2@x.com', 'x')
    wallet.credit(user, 80_000, Transaction.TOPUP)
    client.force_login(user)
    client.post('/health/add/', {'pledge': '1', 
        'name': 'Доктор Валид', 'category': 'gp', 'city': 'Грозный',
        'experience': '5', 'lat': '43.31', 'lon': '45.69',
    })
    assert wallet.balance_of(user) == 30_000  # 50 000 списано за публикацию


def test_doctor_publish_paid_insufficient(client):
    settings_obj = SiteSettings.get_solo()
    settings_obj.doctor_publish_price = 50_000
    settings_obj.save()
    user = User.objects.create_user('d3', 'd3@x.com', 'x')
    client.force_login(user)
    response = client.post('/health/add/', {'pledge': '1', 
        'name': 'Доктор Бедный', 'category': 'gp', 'city': 'Уфа',
        'experience': '3', 'lat': '54.73', 'lon': '55.97',
    })
    assert 'Недостаточно' in response.content.decode()
    from apps.health.models import Doctor

    assert not Doctor.objects.filter(name='Доктор Бедный').exists()  # не создана
