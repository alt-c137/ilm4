import pytest
from django.contrib.auth import get_user_model

from apps.payments.models import TopUp
from apps.payments.services import mark_paid
from apps.wallet import services as wallet

pytestmark = pytest.mark.django_db


def test_mark_paid_credits_once():
    u = get_user_model().objects.create_user('tp', 'tp@x.com', 'pass12345')
    t = TopUp.objects.create(user=u, amount=100_000, provider='card_uz')
    assert mark_paid(t) is True
    assert mark_paid(t) is False            # повторный вебхук не зачисляет дважды
    assert wallet.balance_of(u) == 100_000
