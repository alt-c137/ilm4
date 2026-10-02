"""Попутчики: публикация, поиск (в т.ч. «по пути»), заявки на места, чат поездки, приложение."""
from datetime import timedelta
from datetime import timezone as dt_timezone

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import Moderation, ModuleConfig, SiteSettings
from apps.transport import services
from apps.transport.models import Trip, TripRequest

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def people(db):
    for key in ('transport', 'chat'):
        ModuleConfig.objects.update_or_create(key=key, defaults={'name': key, 'status': 'on'})
    st = SiteSettings.get_solo()
    st.newbie_manual_count = 0
    st.save()
    driver = User.objects.create_user('driver', 'd@x.com', 'x', nickname='Умар')
    rider = User.objects.create_user('rider', 'r@x.com', 'x', nickname='Али')
    return driver, rider


def _trip(owner, **kw):
    data = {'from_city': 'Медина', 'to_city': 'Мекка', 'departs_at': timezone.now() + timedelta(hours=5), 'seats': 3,
            'price': 50, 'currency': 'SAR', 'status': Moderation.APPROVED, 'owner': owner}
    return Trip.objects.create(**{**data, **kw})


def _form(**kw):
    when = (timezone.localtime() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
    return {'role': 'driver', 'from_city': 'Медина', 'to_city': 'Мекка', 'via': 'Джидда', 'departs_at': when,
            'car': 'Toyota Camry, белая', 'seats': 3, 'front_seat': 'on', 'price': 50, 'currency': 'SAR',
            'audience': 'any', 'comment': 'Остановка на намаз', 'pledge': '1', **kw}


def test_trip_is_published_at_once_and_found_by_city_on_the_way(people, client):
    driver, _rider = people
    client.force_login(driver)
    r = client.post('/transport/trips/add/', _form())
    assert r.status_code == 302, r.context['form'].errors if r.context else r.content
    trip = Trip.objects.get()
    assert trip.status == Moderation.APPROVED and trip.front_seat and trip.owner == driver
    client.logout()
    page = client.get('/transport/trips/?from=Джидда').content.decode()        # город «по пути»
    assert 'Медина' in page and 'Toyota Camry' in page and 'переднее свободно' in page
    assert 'Toyota' not in client.get('/transport/trips/?to=Ташкент').content.decode()
    assert client.get(f'/transport/trips/{trip.pk}/').status_code == 200


def test_newbie_trip_waits_for_moderator_and_past_time_is_refused(people, client):
    driver, _rider = people
    st = SiteSettings.get_solo()
    st.newbie_manual_count = 3
    st.save()
    client.force_login(driver)
    client.post('/transport/trips/add/', _form())
    assert Trip.objects.get().status == Moderation.PENDING
    past = (timezone.localtime() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
    r = client.post('/transport/trips/add/', _form(departs_at=past))
    assert r.status_code == 200 and Trip.objects.count() == 1


def test_seat_request_accept_and_cancel(people, client):
    driver, rider = people
    trip = _trip(driver)
    client.force_login(rider)
    client.post(f'/transport/trips/{trip.pk}/request/', {'seats': 2})
    req = TripRequest.objects.get()
    assert req.status == TripRequest.PENDING and req.seats == 2
    # заявка пришла водителю сообщением в чат этой поездки
    from apps.chat.models import Thread
    thread = Thread.objects.get(context_type='trips', context_id=trip.pk)
    assert 'мест — 2' in thread.messages.get().body
    assert Trip.objects.get(pk=trip.pk).seats_left == 3                    # пока не подтверждено — места свободны
    # чужой человек подтвердить не может
    client.post(f'/transport/trips/request/{req.pk}/accept/')
    assert TripRequest.objects.get().status == TripRequest.PENDING
    client.force_login(driver)
    client.post(f'/transport/trips/request/{req.pk}/accept/')
    assert TripRequest.objects.get().status == TripRequest.ACCEPTED and Trip.objects.get(pk=trip.pk).seats_left == 1
    assert thread.messages.count() == 2
    # третий человек просит два места — осталось одно
    other = User.objects.create_user('o', 'o@x.com', 'x')
    with pytest.raises(services.TripError):
        services.request_seat(trip, other, 2)
    services.request_seat(trip, other, 1)
    # попутчик передумал — место освободилось
    client.force_login(rider)
    client.post(f'/transport/trips/request/{req.pk}/cancel/')
    assert Trip.objects.get(pk=trip.pk).seats_left == 3


def test_cannot_book_own_past_or_seeking_trip(people):
    driver, rider = people
    with pytest.raises(services.TripError):
        services.request_seat(_trip(driver), driver, 1)
    with pytest.raises(services.TripError):
        services.request_seat(_trip(driver, departs_at=timezone.now() - timedelta(hours=3)), rider, 1)
    with pytest.raises(services.TripError):
        services.request_seat(_trip(driver, role='passenger'), rider, 1)


def test_past_trips_leave_the_list(people, client):
    driver, _ = people
    _trip(driver, from_city='Ташкент', to_city='Самарканд', departs_at=timezone.now() - timedelta(hours=4))
    _trip(driver)
    page = client.get('/transport/trips/').content.decode()
    assert 'Мекка' in page and 'Самарканд' not in page


def test_trips_in_app_api(people, client):
    from apps.api.models import ApiToken
    driver, rider = people
    trip = _trip(driver, via='Джидда')
    auth = {'HTTP_AUTHORIZATION': 'Bearer ' + ApiToken.issue(rider)}
    lst = client.get('/api/v1/pubs/trips/?q=Джидда', **auth).json()
    assert lst['items'][0]['title'] == 'Медина → Мекка' and 'мест: 3' in lst['items'][0]['subtitle']
    d = client.get(f'/api/v1/pubs/trips/{trip.pk}/', **auth).json()
    assert d['trip'] == {'driver': True, 'seats': 3, 'seats_left': 3, 'past': False, 'my_request': None, 'requests': []}
    r = client.post(f'/api/v1/trips/{trip.pk}/request/', '{"seats": 1}', content_type='application/json', **auth).json()
    assert r['trip']['my_request']['status'] == 'pending'
    owner = {'HTTP_AUTHORIZATION': 'Bearer ' + ApiToken.issue(driver)}
    mine = client.get(f'/api/v1/pubs/trips/{trip.pk}/', **owner).json()
    rid = mine['trip']['requests'][0]['id']
    assert client.post(f'/api/v1/trips/request/{rid}/accept/', **auth).status_code == 403      # не водитель
    ok = client.post(f'/api/v1/trips/request/{rid}/accept/', **owner).json()
    assert ok['trip']['seats_left'] == 2 and ok['trip']['requests'][0]['status'] == 'accepted'
    # форма публикации из приложения: дата со временем и валюта по человеку
    fields = {f['name']: f for f in client.get('/api/v1/pubs/trips/form/', HTTP_X_CURRENCY='SAR', **owner).json()['fields']}
    assert fields['departs_at']['kind'] == 'datetime' and fields['currency']['value'] == 'SAR'


def test_departure_time_is_local_to_the_author(people, client):
    """«14:30» вводится по часам автора и так же показывается всем — в каком бы поясе ни стоял сервер."""
    driver, rider = people
    client.force_login(driver)
    day = (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%d')
    r = client.post('/transport/trips/add/', _form(departs_at=f'{day}T14:30', tz_offset=180))      # Медина, UTC+3
    assert r.status_code == 302
    trip = Trip.objects.get()
    assert trip.tz_offset == 180 and trip.departs_at.astimezone(dt_timezone.utc).hour == 11
    assert trip.departs_local.strftime('%H:%M') == '14:30'
    client.force_login(rider)
    assert '14:30' in client.get(f'/transport/trips/{trip.pk}/').content.decode()
    assert '14:30' in client.get('/transport/trips/').content.decode()
