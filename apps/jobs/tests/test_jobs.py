"""Работа: витрина только одобренных, публикация с договором автора, один отклик."""
import pytest
from django.contrib.auth import get_user_model

from apps.core.models import Moderation
from apps.jobs.models import Vacancy, VacancyResponse

User = get_user_model()
pytestmark = pytest.mark.django_db

DATA = {'title': 'Python-разработчик', 'category': 'it', 'company': 'Халяль-Тех', 'city': 'Ташкент',
        'salary': 'от 1000$', 'description': 'Удалённо, гибкий график, намаз по времени.', 'contact': '@hr'}


def test_list_shows_only_approved(client):
    owner = User.objects.create_user('o', 'o@x.com', 'x')
    Vacancy.objects.create(owner=owner, status=Moderation.APPROVED, **{**DATA, 'title': 'Видна'})
    Vacancy.objects.create(owner=owner, **{**DATA, 'title': 'Скрыта'})
    html = client.get('/jobs/').content.decode()
    assert 'Видна' in html and 'Скрыта' not in html


def test_create_needs_pledge_and_goes_to_moderation(client):
    user = User.objects.create_user('u', 'u@x.com', 'x')
    client.force_login(user)
    client.post('/jobs/add/', DATA)
    assert not Vacancy.objects.exists()
    client.post('/jobs/add/', {**DATA, 'pledge': '1'})
    assert Vacancy.objects.get().status == Moderation.PENDING


def test_respond_once_and_not_to_own(client):
    owner = User.objects.create_user('o', 'o@x.com', 'x')
    v = Vacancy.objects.create(owner=owner, status=Moderation.APPROVED, **DATA)
    seeker = User.objects.create_user('s', 's@x.com', 'x')
    client.force_login(seeker)
    client.post(f'/jobs/{v.pk}/respond/', {'message': 'Здравствуйте, есть опыт 3 года'})
    client.post(f'/jobs/{v.pk}/respond/', {'message': 'Ещё раз'})
    assert VacancyResponse.objects.count() == 1
    client.force_login(owner)
    client.post(f'/jobs/{v.pk}/respond/', {'message': 'Сам себе'})
    assert VacancyResponse.objects.count() == 1
