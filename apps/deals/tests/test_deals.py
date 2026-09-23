"""Безопасная сделка: деньги двигаются строго по шагам, без потерь и двойных выплат."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import SiteSettings
from apps.deals import services
from apps.deals.models import Order
from apps.wallet import services as wallet
from apps.wallet.models import Transaction

pytestmark = pytest.mark.django_db
U = get_user_model()


@pytest.fixture
def people():
    st = SiteSettings.get_solo()
    st.escrow_enabled = True
    st.escrow_fee_percent = Decimal(5)
    st.save()
    client = U.objects.create_user('cl', 'cl@x.com', 'pass12345')
    prov = U.objects.create_user('pr', 'pr@x.com', 'pass12345')
    admin = U.objects.create_user('ad', 'ad@x.com', 'pass12345', is_staff=True)
    wallet.credit(client, 1_000_000, Transaction.TOPUP)
    return client, prov, admin


def test_happy_path_with_fee(people):
    client, prov, _ = people
    o = services.create(client, prov, 'Логотип', 'Три варианта, 2 правки', 200_000)
    services.accept(o, prov)
    services.fund(o, client)
    assert wallet.balance_of(client) == 800_000            # удержано
    assert wallet.balance_of(prov) == 0
    services.deliver(o, prov)
    services.complete(Order.objects.get(pk=o.pk), client)
    assert wallet.balance_of(prov) == 190_000              # 200 000 − 5 %
    o.refresh_from_db()
    assert o.status == Order.COMPLETED and o.escrow.fee == 10_000
    with pytest.raises(services.DealError):               # повторная выплата невозможна
        services.complete(o, client)


def test_dispute_refund(people):
    client, prov, admin = people
    o = services.create(client, prov, 'Сайт', 'Лендинг', 300_000)
    services.accept(o, prov)
    services.fund(o, client)
    services.dispute(o, client, 'Не сдал в срок')
    services.resolve(Order.objects.get(pk=o.pk), admin, to_provider=False)
    assert wallet.balance_of(client) == 1_000_000 and wallet.balance_of(prov) == 0


def test_roles_enforced(people):
    client, prov, _ = people
    o = services.create(client, prov, 'Текст', 'Статья', 50_000)
    with pytest.raises(services.DealError):
        services.accept(o, client)                         # принимает только исполнитель
    services.accept(o, prov)
    with pytest.raises(services.DealError):
        services.fund(o, prov)                             # платит только заказчик


def test_insufficient_funds_nothing_moves(people):
    client, prov, _ = people
    o = services.create(client, prov, 'Дорого', 'Очень', 5_000_000)
    services.accept(o, prov)
    with pytest.raises(wallet.InsufficientFunds):
        services.fund(o, client)
    o.refresh_from_db()
    assert o.status == Order.ACCEPTED and wallet.balance_of(client) == 1_000_000


def test_auto_release(people):
    client, prov, _ = people
    o = services.create(client, prov, 'Перевод', 'Документ', 100_000)
    services.accept(o, prov)
    services.fund(o, client)
    services.deliver(o, prov)
    Order.objects.filter(pk=o.pk).update(delivered_at=timezone.now() - timedelta(days=10))
    assert services.release_due() == 1
    assert wallet.balance_of(prov) == 95_000


def test_disabled_blocks_create(people):
    client, prov, _ = people
    SiteSettings.objects.update(escrow_enabled=False)
    with pytest.raises(services.DealError):
        services.create(client, prov, 'x', 'y', 1000)
