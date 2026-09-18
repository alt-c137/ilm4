"""Фаза 2 — кошелёк: атомарность, инварианты, эскроу, вывод (ARCHITECTURE.md §5)."""
import unittest
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from apps.wallet import services
from apps.wallet.models import EscrowDeal, PayoutRequest, Transaction
from apps.wallet.services import InsufficientFunds

User = get_user_model()


@pytest.fixture
def alice():
    return User.objects.create_user('alice', 'alice@x.com', 'x')


@pytest.fixture
def bob():
    return User.objects.create_user('bob', 'bob@x.com', 'x')


@pytest.mark.django_db
def test_credit_and_debit(alice):
    services.credit(alice, 100_000, Transaction.TOPUP)
    services.credit(alice, 50_000, Transaction.EARN)
    assert services.balance_of(alice) == Decimal(150000)

    tx = services.debit(alice, 60_000, Transaction.PURCHASE, ref='test:boost')
    assert services.balance_of(alice) == Decimal(90000)
    assert tx.balance_after == Decimal(90000)
    assert alice.transactions.count() == 3  # журнал полный


@pytest.mark.django_db
def test_debit_insufficient_keeps_balance(alice):
    services.credit(alice, 10_000, Transaction.TOPUP)
    with pytest.raises(InsufficientFunds):
        services.debit(alice, 11_000, Transaction.PURCHASE)
    assert services.balance_of(alice) == Decimal(10000)  # баланс не тронут


@pytest.mark.django_db
def test_wrong_kind_rejected(alice):
    with pytest.raises(ValueError):
        services.credit(alice, 100, Transaction.PURCHASE)  # списание нельзя вызвать как зачисление
    with pytest.raises(ValueError):
        services.debit(alice, 100, Transaction.TOPUP)


@pytest.mark.django_db
def test_ledger_consistency(alice):
    """Инвариант: баланс == сумма зачислений − сумма списаний."""
    services.credit(alice, 500_000, Transaction.TOPUP)
    services.debit(alice, 120_000, Transaction.PURCHASE)
    services.credit(alice, 30_000, Transaction.EARN)
    services.debit(alice, 50_000, Transaction.PAYOUT)
    credits = sum((t.amount for t in alice.transactions.all()
                   if t.kind in Transaction.CREDIT_KINDS), Decimal(0))
    debits = sum((t.amount for t in alice.transactions.all()
                  if t.kind in Transaction.DEBIT_KINDS), Decimal(0))
    assert services.balance_of(alice) == credits - debits == Decimal(360000)


@unittest.skipIf(
    connection.vendor == 'sqlite',
    'Гонка проверяется на PostgreSQL (прод-БД): в SQLite select_for_update — no-op',
)
class ConcurrentDebitTest(TransactionTestCase):
    """Гонка: параллельные списания не должны уводить баланс в минус.

    Два потока одновременно списывают по 800 при балансе 1000 — пройти должен
    ровно один (блокировка select_for_update), второй — InsufficientFunds.
    """

    def test_parallel_debits(self):
        import threading

        alice = User.objects.create_user('alice', 'alice@x.com', 'x')
        services.credit(alice, 1000, Transaction.TOPUP)

        barrier = threading.Barrier(2)
        results = []

        def worker():
            close_old_connections()
            barrier.wait()
            try:
                services.debit(alice, 800, Transaction.PURCHASE)
                results.append('ok')
            except InsufficientFunds:
                results.append('blocked')

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # ровно одно списание прошло (800 <= 1000), второе заблокировано
        assert sorted(results) == ['blocked', 'ok']
        assert services.balance_of(alice) == Decimal(200)


@pytest.mark.django_db
def test_escrow_full_cycle(alice, bob):
    services.credit(alice, 70_000, Transaction.TOPUP)
    deal = services.escrow_hold(alice, bob, 70_000, ref='market:order:1')
    assert deal.status == EscrowDeal.HOLD
    assert services.balance_of(alice) == 0  # деньги заморожены (списаны у покупателя)
    assert services.balance_of(bob) == 0

    services.escrow_release(deal)
    deal.refresh_from_db()
    assert deal.status == EscrowDeal.RELEASED
    assert services.balance_of(bob) == Decimal(70000)

    with pytest.raises(ValueError):  # повторное решение запрещено
        services.escrow_refund(deal)
    assert services.balance_of(bob) == Decimal(70000)  # двойной выплаты нет


@pytest.mark.django_db
def test_escrow_refund(alice, bob):
    services.credit(alice, 50_000, Transaction.TOPUP)
    deal = services.escrow_hold(alice, bob, 50_000)
    services.escrow_refund(deal)
    assert services.balance_of(alice) == Decimal(50000)
    assert services.balance_of(bob) == 0


@pytest.mark.django_db
def test_payout_flow(alice):
    services.credit(alice, 200_000, Transaction.TOPUP)
    req = services.create_payout_request(alice, 150_000, min_amount=Decimal(100000))
    assert services.balance_of(alice) == Decimal(50000)  # сумма ушла с баланса

    services.reject_payout(req, decided_by=None)
    assert services.balance_of(alice) == Decimal(200000)  # вернулась
    req.refresh_from_db()
    assert req.status == PayoutRequest.REJECTED


@pytest.mark.django_db
def test_payout_below_min(alice):
    services.credit(alice, 90_000, Transaction.TOPUP)
    with pytest.raises(ValueError):
        services.create_payout_request(alice, 90_000, min_amount=Decimal(100000))
    assert services.balance_of(alice) == Decimal(90000)


@pytest.mark.django_db
def test_wallet_page_requires_login(client):
    response = client.get('/wallet/')
    assert response.status_code == 302 and '/accounts/login' in response.url
