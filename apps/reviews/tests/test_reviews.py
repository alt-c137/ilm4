"""Отзывы: одна оценка на человека, себя не оценить, скрытые не считаются."""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from apps.reviews.models import Review
from apps.reviews.services import summary

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def seller():
    return User.objects.create_user('seller', 's@x.com', 'pass12345')


@pytest.fixture
def buyer():
    return User.objects.create_user('buyer', 'b@x.com', 'pass12345')


def url(obj):
    return f'/reviews/{ContentType.objects.get_for_model(obj).pk}/{obj.pk}/'


def test_review_and_update(client, seller, buyer):
    client.force_login(buyer)
    client.post(url(seller), {'rating': '5', 'text': 'Отлично', 'next': '/'})
    client.post(url(seller), {'rating': '3', 'text': 'Передумал', 'next': '/'})
    assert Review.objects.count() == 1
    assert summary(seller) == {'avg': 3.0, 'count': 1, 'full': 3, 'half': False}


def test_cannot_review_self(client, seller):
    client.force_login(seller)
    client.post(url(seller), {'rating': '5', 'next': '/'})
    assert Review.objects.count() == 0


def test_hidden_not_counted_and_bad_rating(client, seller, buyer):
    client.force_login(buyer)
    client.post(url(seller), {'rating': '9', 'next': '/'})
    assert Review.objects.count() == 0
    client.post(url(seller), {'rating': '4', 'next': '/'})
    Review.objects.update(is_hidden=True)
    assert summary(seller)['count'] == 0


def test_public_profile_and_verified_badge(client, seller):
    seller.platform_verified = True
    seller.save()
    html = client.get(f'/accounts/u/{seller.pk}/').content.decode()
    assert 'Проверено ilm4' in html and 'не гарантия качества' in html
