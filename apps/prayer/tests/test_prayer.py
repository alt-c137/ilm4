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


def test_until_next_today_and_tomorrow():
    times = services.compute(41.3111, 69.2797, 5)
    # днём — следующий намаз сегодня
    info = services.until_next(times, now=datetime(2026, 9, 19, 10, 0))
    assert info['key'] == 'dhuhr' and not info['tomorrow']
    assert 'ч' in info['human'] and info['time'] == times['dhuhr']
    # после Иши — завтрашний Фаджр, и остаток считается честно
    # (ожидание считается от фактических времён — они сдвигаются с датами)
    info = services.until_next(times, now=datetime(2026, 9, 19, 23, 30))
    assert info['key'] == 'fajr' and info['tomorrow'] and info['time'] == times['fajr']
    fajr_m = int(times['fajr'][:2]) * 60 + int(times['fajr'][3:])
    expected = (1440 - (23 * 60 + 30)) + fajr_m
    h, m = divmod(expected, 60)
    assert info['human'] == f'{h} ч {m:02d} мин'


def test_progress_between_prayers():
    times = services.compute(41.3111, 69.2797, 5)
    # 10:00 — между Фаджром (04:34) и Зухром (12:17) — где-то посередине, не 0 и не 100
    pct = services.prayer_progress(times, now=datetime(2026, 9, 19, 10, 0))
    assert 0 < pct < 100
    # после Иши (20:00) прогресс идёт к завтрашнему Фаджру и не упирается в 100% сразу
    pct_night = services.prayer_progress(times, now=datetime(2026, 9, 19, 21, 0))
    assert 0 < pct_night < 100


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


def test_makkah_isha_after_maghrib():
    """Умм аль-Кура: Иша = Магриб + 90 мин (регресс: порт praytimes ломал порядок)."""
    times = services.compute(41.3111, 69.2797, 5, method='Makkah')
    def mins(t):
        h, m = t.split(':')
        return int(h) * 60 + int(m)
    assert mins(times['isha']) > mins(times['maghrib'])
    assert mins(times['isha']) - mins(times['maghrib']) == 90


def test_next_epoch_future():
    import time as _time
    times = services.compute(41.3111, 69.2797, 5)
    ts = services.next_epoch(times)
    assert ts > _time.time() - 120  # в будущем (или только что наступил)
