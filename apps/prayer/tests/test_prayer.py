"""Фаза 3 — время намаза: расчёт, страница, витрина, вкл/выкл раздела."""
from datetime import datetime

import pytest

from apps.core.models import ModuleConfig
from apps.prayer import services

pytestmark = pytest.mark.django_db


def test_compute_returns_all_times_in_order():
    times = services.compute(41.3111, 69.2797, 5)  # Ташкент
    assert set(times) == {'fajr', 'sunrise', 'dhuhr', 'asr', 'maghrib', 'isha'}
    parsed = [datetime.strptime(times[k], '%H:%M') for k in services.NAMES]
    assert parsed == sorted(parsed)  # времена растут в течение дня


def test_compute_city_key():
    times = services.compute_for_city('kazan')
    assert all(t for t in times.values())  # всё посчитано, без пустых


def test_next_prayer():
    times = services.compute(41.3111, 69.2797, 5)
    key, name, left = services.next_prayer(times, now=datetime.strptime('01:00', '%H:%M'))
    assert key == 'fajr' and name == 'Фаджр'
    # после Иши ближайший — Фаджр завтра
    key, _, left = services.next_prayer(times, now=datetime.strptime('23:59', '%H:%M'))
    assert key == 'fajr' and left == 'завтра'


def test_prayer_page_available(client):
    assert ModuleConfig.objects.filter(key='prayer', status='on').exists()
    response = client.get('/prayer/')
    assert response.status_code == 200
    assert 'Фаджр' in response.content.decode()


def test_prayer_page_city(client):
    response = client.get('/prayer/', {'city': 'kazan'})
    assert response.status_code == 200
    assert 'Казань' in response.content.decode()


def test_prayer_page_gps(client):
    response = client.get('/prayer/', {'lat': '41.0', 'lon': '69.0', 'tz': '5'})
    assert response.status_code == 200
    assert 'Моё местоположение' in response.content.decode()


def test_prayer_disabled_returns_404(client):
    ModuleConfig.objects.filter(key='prayer').update(status='off')
    assert client.get('/prayer/').status_code == 404


def test_widget_on_homepage(client):
    response = client.get('/')
    html = response.content.decode()
    assert 'Время намаза' in html       # блок на главной
    assert 'Ближайший намаз' in html
