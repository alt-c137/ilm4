"""Миграция: истории — на модерацию, с договором автора, без пустых записей."""
import pytest
from django.contrib.auth import get_user_model

from apps.core.models import Moderation
from apps.migration.models import Story

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_story_create_and_moderation(client):
    user = User.objects.create_user('u', 'u@x.com', 'x')
    client.force_login(user)
    data = {'title': 'Как я переехал в Турцию', 'country_from': 'Узбекистан', 'country_to': 'Турция',
            'body': 'Документы, работа, жильё — по шагам.'}
    client.post('/migration/add/', data)                 # без договора автора
    assert not Story.objects.exists()
    client.post('/migration/add/', {**data, 'title': '', 'pledge': '1'})   # пустой заголовок
    assert not Story.objects.exists()
    client.post('/migration/add/', {**data, 'pledge': '1'})
    story = Story.objects.get()
    assert story.status == Moderation.PENDING
    assert 'Как я переехал' not in client.get('/migration/').content.decode()
