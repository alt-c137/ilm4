"""Врачи: каталог, публикация только после входа и с договором автора."""
import pytest
from django.contrib.auth import get_user_model

from apps.health.models import Doctor

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_catalog_renders(client):
    assert client.get('/health/').status_code == 200


def test_add_requires_login(client):
    resp = client.get('/health/add/')
    assert resp.status_code == 302 and '/accounts/login/' in resp.url


def test_add_doctor_goes_to_moderation(client):
    user = User.objects.create_user('d', 'd@x.com', 'x')
    client.force_login(user)
    category = Doctor._meta.get_field('category').choices[0][0]
    data = {'name': 'Др. Юсуф', 'category': category, 'city': 'Ташкент', 'clinic': 'Шифа',
            'experience': '10', 'address': 'ул. Навои, 1', 'lat': '41.31', 'lon': '69.28',
            'phone': '+998 90 000 00 00', 'description': 'Терапевт, хиджама', 'pledge': '1'}
    client.post('/health/add/', data)
    doc = Doctor.objects.get()
    assert doc.owner == user and doc.status == 'pending'
