"""Каждую «тяжёлую» функцию можно выключить в админке — и она действительно закрывается."""
import pytest
from django.contrib.auth import get_user_model

from apps.core.models import ModuleConfig, SiteSettings

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(client):
    ModuleConfig.objects.update_or_create(key='chat', defaults={'name': 'Чат', 'status': 'on'})
    u = get_user_model().objects.create_user('tg', 'tg@x.com', 'pass12345')
    client.force_login(u)
    return u


def test_feed_toggle(client, user):
    assert client.get('/feed/').status_code == 200
    SiteSettings.objects.update(feed_enabled=False)
    assert client.get('/feed/').status_code == 404
    assert '/feed/' not in client.get('/catalog/').content.decode()


def test_contacts_toggle(client, user):
    assert client.get('/chat/contacts/').status_code == 200
    SiteSettings.objects.update(chat_contacts_enabled=False)
    assert client.get('/chat/contacts/').status_code == 404
    assert client.post('/chat/contacts/match/', '{}', content_type='application/json').status_code == 404


def test_calls_toggle_hides_buttons(client, user):
    from apps.chat.models import Thread
    other = get_user_model().objects.create_user('tg2', 'tg2@x.com', 'pass12345')
    t = Thread.objects.create()
    t.participants.add(user, other)
    html = client.get(f'/chat/{t.pk}/').content.decode()
    assert 'data-call="audio"' in html and 'id="mic-btn"' in html
    SiteSettings.objects.update(chat_calls_enabled=False, chat_video_calls_enabled=False,
                                chat_voice_enabled=False, chat_circles_enabled=False, chat_photos_enabled=False,
                                chat_videos_enabled=False)
    html = client.get(f'/chat/{t.pk}/').content.decode()
    for marker in ('data-call="audio"', 'data-call="video"', 'id="mic-btn"', 'id="circle-btn"', 'id="photo-input"'):
        assert marker not in html
    assert 'data-calls="1"' not in html          # фоновое ожидание звонков тоже выключено
