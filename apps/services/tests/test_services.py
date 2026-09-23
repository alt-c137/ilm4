"""Услуги: публикация с договором автора, витрина только одобренных."""
import pytest
from django.contrib.auth import get_user_model

from apps.core.models import Moderation
from apps.services.models import Service

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_service_flow(client):
    user = User.objects.create_user('u', 'u@x.com', 'x')
    client.force_login(user)
    data = {'name': 'Нотариальный перевод', 'kind': 'translate', 'city': 'Ташкент',
            'description': 'Переводы с арабского и турецкого', 'price_text': 'от 50 000', 'contact': '@tr'}
    client.post('/services/add/', data)
    assert not Service.objects.exists()
    client.post('/services/add/', {**data, 'pledge': '1'})
    s = Service.objects.get()
    assert s.status == Moderation.PENDING
    assert 'Нотариальный перевод' not in client.get('/services/').content.decode()
    Service.objects.filter(pk=s.pk).update(status=Moderation.APPROVED)
    assert 'Нотариальный перевод' in client.get('/services/').content.decode()
