"""Аналитика использования: время по разделам, возвращаемость, страница владельца, порядок ленты по интересам."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import ModuleConfig
from apps.metrics import services
from apps.metrics.models import Use

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_time_is_counted_per_section(client):
    ModuleConfig.objects.update_or_create(key='chat', defaults={'name': 'Чат', 'status': 'on'})
    u = User.objects.create_user('mx', 'mx@x.com', 'x')
    client.force_login(u)
    assert client.post('/m/', {'s': 'chat', 't': 30, 'o': 1}).status_code == 204
    client.post('/m/', {'s': 'chat', 't': 30, 'o': 0})
    client.post('/m/', {'s': 'chat', 't': 99999, 'o': 0})                    # накрутка обрезается до MAX_BEAT
    client.post('/m/', {'s': 'нет-такого', 't': 10, 'o': 1})
    row = Use.objects.get(user=u, section='chat')
    assert (row.seconds, row.opens) == (60 + services.MAX_BEAT, 1) and Use.objects.filter(section='other').exists()
    guest = type(client)()
    guest.post('/m/', {'s': 'home', 't': 5, 'o': 1})
    assert Use.objects.filter(user__isnull=True, section='home').count() == 1 and 'ilm4_v' in guest.cookies


def test_retention_and_owner_page(client):
    old = User.objects.create_user('r1', 'r1@x.com', 'x')
    gone = User.objects.create_user('r2', 'r2@x.com', 'x')
    User.objects.filter(pk__in=[old.pk, gone.pk]).update(date_joined=timezone.now() - timedelta(days=7))
    today = timezone.localdate()
    Use.objects.create(user=old, day=today, section='chat', seconds=600, opens=3)          # вернулся на 7-й день
    day7 = next(r for r in services.retention() if r['day'] == '7')
    assert (day7['cohort'], day7['back'], day7['rate']) == (2, 1, 50)
    data = services.summary(30)
    assert data['dau'] == 1 and data['sections'][0]['section'] == 'chat' and data['sections'][0]['minutes'] == 10
    assert client.get('/moderation/stats/').status_code == 302                              # только сотрудникам
    admin = User.objects.create_superuser('adm', 'adm@x.com', 'x')
    client.force_login(admin)
    session = client.session
    session.save()
    page = client.get('/moderation/stats/', follow=True)
    assert page.status_code == 200


def test_feed_follows_interests():
    from apps.social import services as social
    me = User.objects.create_user('f1', 'f1@x.com', 'x')
    liked_author = User.objects.create_user('f2', 'f2@x.com', 'x')
    stranger = User.objects.create_user('f3', 'f3@x.com', 'x')
    old = social.create_post(liked_author, 'старая запись любимого автора', [])
    earlier = social.create_post(liked_author, 'ещё одна', [])
    social.like(me, earlier.key)
    social.save(me, earlier.key)
    type(old).objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=3))
    fresh = social.create_post(stranger, 'свежая запись незнакомца', [])
    type(fresh).objects.filter(pk=fresh.pk).update(created_at=timezone.now() - timedelta(hours=1))
    type(earlier).objects.filter(pk=earlier.pk).update(created_at=timezone.now() - timedelta(hours=30))
    keys = [x['key'] for x in social.feed(me)['items'] if x['kind'] == 'post']
    assert keys.index(old.key) < keys.index(fresh.key)                                      # интерес важнее пары часов свежести
    guest_keys = [x['key'] for x in social.feed(stranger)['items'] if x['kind'] == 'post']
    assert guest_keys.index(fresh.key) < guest_keys.index(old.key)                          # без интересов — просто по времени
    assert social.saved_items(me)[0]['key'] == earlier.key and social.feed(me)['items'][0].get('saved') is not None
