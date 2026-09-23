"""Фаза 5 — ilmbuy: модерация, фильтры, буст за деньги."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import Moderation, SiteSettings
from apps.market.models import Category, Listing
from apps.wallet import services as wallet
from apps.wallet.models import Transaction

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user('seller', 's@x.com', 'x')


@pytest.fixture
def cat():
    return Category.objects.get(slug='electronics')  # из сидинга


def make_listing(user, cat, title='iPhone 14', status=Moderation.APPROVED, city='Ташкент', **kw):
    return Listing.objects.create(
        title=title, description='Состояние идеальное', price=720, currency='USD',
        category=cat, city=city, owner=user, status=status, **kw,
    )


def test_pending_hidden(client, user, cat):
    make_listing(user, cat, status=Moderation.PENDING)
    assert 'iPhone 14' not in client.get('/buy/').content.decode()


def test_approved_visible_with_filters(client, user, cat):
    make_listing(user, cat)
    make_listing(user, cat, title='Молитвенный коврик', city='Самарканд')
    html = client.get('/buy/', {'city': 'Самарканд'}).content.decode()
    assert 'Молитвенный коврик' in html and 'iPhone 14' not in html
    html = client.get('/buy/', {'q': 'ковр'}).content.decode()
    assert 'Молитвенный коврик' in html
    html = client.get('/buy/', {'cat': 'electronics'}).content.decode()
    assert 'iPhone 14' in html


def test_create_with_moderation(client, user, cat):
    client.force_login(user)
    client.post('/buy/add/', {'pledge': '1', 
        'title': 'Ноутбук ASUS', 'description': 'Рабочий',
        'price': '540', 'currency': 'USD', 'category': cat.pk, 'city': 'Ташкент',
    })
    listing = Listing.objects.get(title='Ноутбук ASUS')
    assert listing.status == Moderation.PENDING
    assert listing.owner == user


def test_create_without_moderation(client, user, cat):
    settings_obj = SiteSettings.get_solo()
    settings_obj.market_moderation = False
    settings_obj.save()
    client.force_login(user)
    client.post('/buy/add/', {'pledge': '1', 
        'title': 'Финики', 'description': 'Аджва',
        'price': '28000', 'currency': 'UZS', 'category': cat.pk, 'city': 'Бухара',
    })
    assert Listing.objects.get(title='Финики').status == Moderation.APPROVED


def test_boost_debits_and_raises(client, user, cat):
    wallet.credit(user, 50_000, Transaction.TOPUP)
    listing = make_listing(user, cat)
    client.force_login(user)
    client.post(f'/buy/{listing.pk}/boost/')
    listing.refresh_from_db()
    assert listing.is_boosted
    assert listing.boosted_until > timezone.now() + timedelta(days=6)
    assert wallet.balance_of(user) == 30_000  # 20 000 (дефолт) списано


def test_boost_insufficient(client, user, cat):
    listing = make_listing(user, cat)
    client.force_login(user)
    response = client.post(f'/buy/{listing.pk}/boost/')
    assert response.status_code == 302 and '/wallet/' in response.url
    listing.refresh_from_db()
    assert not listing.is_boosted


def test_detail_page(client, user, cat):
    listing = make_listing(user, cat)
    response = client.get(f'/buy/{listing.pk}/')
    assert response.status_code == 200
    assert 'iPhone 14' in response.content.decode()


def test_only_own_listing_boost(client, user, cat):
    other = User.objects.create_user('other', 'o@x.com', 'x')
    listing = make_listing(other, cat)
    client.force_login(user)
    response = client.post(f'/buy/{listing.pk}/boost/')
    assert response.status_code == 404


def test_create_requires_pledge(client):
    """Без «Договора перед Аллахом» объявление не публикуется."""
    from apps.market.models import Listing
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.create_user('pl', 'pl@x.com', 'pass12345')
    client.force_login(user)
    before = Listing.objects.count()
    response = client.post('/buy/add/', {'title': 'Без договора', 'description': 'x', 'price': '1',
                                         'currency': 'UZS', 'city': 'Ташкент'})
    assert response.status_code == 302
    assert Listing.objects.count() == before
