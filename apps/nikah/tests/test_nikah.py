"""Фаза 7 — никах: модерация, платный контакт для мужчин, бесплатный для женщин."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import Moderation
from apps.nikah.models import NikahContact, NikahProfile
from apps.wallet import services as wallet
from apps.wallet.models import Transaction

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_profile(user, gender, status=Moderation.APPROVED):
    return NikahProfile.objects.create(
        user=user, gender=gender, age=25, city='Ташкент',
        about='Серьёзные намерения, работаю, учусь', contact_hint='tg @test',
        status=status,
    )


def test_pending_hidden(client):
    owner = User.objects.create_user('o', 'o@x.com', 'x')
    make_profile(owner, 'F', status=Moderation.PENDING)
    assert 'Сестра' not in client.get('/nikah/').content.decode()


def test_male_pays_for_contact(client):
    sister = User.objects.create_user('s', 's@x.com', 'x')
    profile = make_profile(sister, 'F')
    brother = User.objects.create_user('b', 'b@x.com', 'x')
    make_profile(brother, 'M')  # анкета брата задаёт пол
    wallet.credit(brother, 50_000, Transaction.TOPUP)
    client.force_login(brother)

    client.post(f'/nikah/{profile.pk}/contact/')
    assert NikahContact.objects.filter(from_user=brother).exists()
    assert wallet.balance_of(brother) == 40_000  # 10 000 (дефолт) списано

    client.post(f'/nikah/{profile.pk}/contact/')  # повторно — бесплатно
    assert wallet.balance_of(brother) == 40_000
    assert NikahContact.objects.count() == 1


def test_female_contact_free(client):
    brother = User.objects.create_user('b2', 'b2@x.com', 'x')
    profile = make_profile(brother, 'M')
    sister = User.objects.create_user('s2', 's2@x.com', 'x')
    make_profile(sister, 'F')
    client.force_login(sister)

    client.post(f'/nikah/{profile.pk}/contact/')
    assert NikahContact.objects.filter(from_user=sister).exists()
    assert wallet.balance_of(sister) == 0  # бесплатно


def test_male_insufficient_no_contact(client):
    sister = User.objects.create_user('s3', 's3@x.com', 'x')
    profile = make_profile(sister, 'F')
    brother = User.objects.create_user('b3', 'b3@x.com', 'x')
    make_profile(brother, 'M')
    client.force_login(brother)

    response = client.post(f'/nikah/{profile.pk}/contact/')
    assert response.status_code == 302 and '/wallet/' in response.url
    assert not NikahContact.objects.exists()  # контакт не создан без денег


def test_contact_shown_after_payment(client):
    sister = User.objects.create_user('s4', 's4@x.com', 'x')
    profile = make_profile(sister, 'F')
    brother = User.objects.create_user('b4', 'b4@x.com', 'x')
    make_profile(brother, 'M')
    wallet.credit(brother, 50_000, Transaction.TOPUP)
    client.force_login(brother)
    client.post(f'/nikah/{profile.pk}/contact/')
    html = client.get(f'/nikah/{profile.pk}/').content.decode()
    assert 'tg @test' in html  # контакт открыт


def test_boost_profile(client):
    sister = User.objects.create_user('s5', 's5@x.com', 'x')
    profile = make_profile(sister, 'F')
    wallet.credit(sister, 30_000, Transaction.TOPUP)
    client.force_login(sister)
    client.post('/nikah/boost/')
    profile.refresh_from_db()
    assert profile.is_boosted
    assert wallet.balance_of(sister) == 15_000  # 15 000 (дефолт) списано
