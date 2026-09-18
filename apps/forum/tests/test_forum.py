"""Фаза 6 — форум: модерация тем, ответы."""
import pytest
from django.contrib.auth import get_user_model

from apps.core.models import Moderation
from apps.forum.models import Topic

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_topic(status=Moderation.APPROVED):
    user = User.objects.create_user('asker', 'a@x.com', 'x')
    return Topic.objects.create(title='Можно ли объединять намазы в дороге?',
                                body='Еду ночью', author=user, status=status)


def test_pending_topic_hidden(client):
    make_topic(status=Moderation.PENDING)
    assert 'объединять' not in client.get('/forum/').content.decode()


def test_approved_topic_and_reply(client):
    topic = make_topic()
    responder = User.objects.create_user('r', 'r@x.com', 'x')
    client.force_login(responder)
    client.post(f'/forum/{topic.pk}/reply/', {'body': 'Да, в пути — можно.'})
    html = client.get(f'/forum/{topic.pk}/').content.decode()
    assert 'Да, в пути — можно.' in html
    assert '1 ответ' in html or 'ответ' in html
