"""Сервисы кошелька — ЕДИНСТВЕННЫЙ способ менять баланс (ARCHITECTURE.md §5).

Все операции атомарны: строка Wallet блокируется select_for_update,
поэтому параллельные списания не задваивают и не уводят баланс в минус.
Из других приложений вызывать только эти функции, не трогая таблицы напрямую.
"""
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from .models import EscrowDeal, PayoutRequest, Transaction, Wallet


class InsufficientFunds(Exception):
    """Недостаточно средств для списания."""


def balance_of(user) -> Decimal:
    """Текущий баланс (кошелёк создаётся при первом обращении)."""
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet.balance


def _locked_wallet(user):
    """Кошелёк с блокировкой строки — внутри atomic."""
    wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
    return wallet


@db_transaction.atomic
def credit(user, amount, kind: str, ref: str = '', note: str = '') -> Transaction:
    """Зачислить (пополнение/эскроу-выплата/корректировка)."""
    amount = Decimal(amount)
    if amount <= 0:
        raise ValueError('Сумма должна быть положительной')
    if kind not in Transaction.CREDIT_KINDS:
        raise ValueError(f'{kind} не является зачислением')
    wallet = _locked_wallet(user)
    wallet.balance += amount
    wallet.save(update_fields=['balance', 'updated_at'])
    return Transaction.objects.create(
        user=user, amount=amount, kind=kind, ref=ref, note=note,
        balance_after=wallet.balance,
    )


@db_transaction.atomic
def debit(user, amount, kind: str, ref: str = '', note: str = '') -> Transaction:
    """Списать (платное действие/вывод/эскроу-заморозка). Не хватает — исключение."""
    amount = Decimal(amount)
    if amount <= 0:
        raise ValueError('Сумма должна быть положительной')
    if kind not in Transaction.DEBIT_KINDS:
        raise ValueError(f'{kind} не является списанием')
    wallet = _locked_wallet(user)
    if wallet.balance < amount:
        raise InsufficientFunds(
            f'Недостаточно средств: баланс {wallet.balance}, нужно {amount}')
    wallet.balance -= amount
    wallet.save(update_fields=['balance', 'updated_at'])
    return Transaction.objects.create(
        user=user, amount=amount, kind=kind, ref=ref, note=note,
        balance_after=wallet.balance,
    )


# ---------- эскроу ----------

@db_transaction.atomic
def escrow_hold(buyer, seller, amount, ref: str = '') -> EscrowDeal:
    """Заморозить деньги покупателя под сделку (списание сразу)."""
    amount = Decimal(amount)
    if amount <= 0:
        raise ValueError('Сумма должна быть положительной')
    if buyer == seller:
        raise ValueError('Покупатель и продавец совпадают')
    deal = EscrowDeal.objects.create(buyer=buyer, seller=seller, amount=amount, ref=ref)
    debit(buyer, amount, Transaction.ESCROW_HOLD, ref=ref or f'escrow:{deal.id}',
          note=f'Эскроу-сделка #{deal.id}')
    return deal


@db_transaction.atomic
def escrow_release(deal: EscrowDeal, decided_by=None) -> EscrowDeal:
    """Выплатить продавцу (арбитраж). Повторное решение запрещено."""
    _assert_hold(deal)
    credit(deal.seller, deal.amount, Transaction.ESCROW_RELEASE,
           ref=f'escrow:{deal.id}', note=f'Эскроу-сделка #{deal.id} выплачена')
    deal.status = EscrowDeal.RELEASED
    deal.resolved_at = timezone.now()
    deal.save(update_fields=['status', 'resolved_at', 'note'])
    return deal


@db_transaction.atomic
def escrow_refund(deal: EscrowDeal, decided_by=None) -> EscrowDeal:
    """Вернуть покупателю (арбитраж). Повторное решение запрещено."""
    _assert_hold(deal)
    credit(deal.buyer, deal.amount, Transaction.ESCROW_REFUND,
           ref=f'escrow:{deal.id}', note=f'Эскроу-сделка #{deal.id} возвращена')
    deal.status = EscrowDeal.REFUNDED
    deal.resolved_at = timezone.now()
    deal.save(update_fields=['status', 'resolved_at', 'note'])
    return deal


def _assert_hold(deal):
    if deal.status != EscrowDeal.HOLD:
        raise ValueError(f'Сделка уже решена: {deal.get_status_display()}')


# ---------- вывод средств ----------

@db_transaction.atomic
def create_payout_request(user, amount, min_amount: Decimal) -> PayoutRequest:
    """Заявка на вывод: списание сразу, при отклонении админ возвращает."""
    amount = Decimal(amount)
    if amount < min_amount:
        raise ValueError(f'Минимальная сумма вывода: {min_amount}')
    request = PayoutRequest.objects.create(user=user, amount=amount)
    debit(user, amount, Transaction.PAYOUT, ref=f'payout:{request.id}',
          note=f'Заявка на вывод #{request.id}')
    return request


@db_transaction.atomic
def reject_payout(request: PayoutRequest, decided_by) -> PayoutRequest:
    """Отклонить заявку — деньги возвращаются на баланс."""
    if request.status != PayoutRequest.PENDING:
        raise ValueError('Заявка уже обработана')
    credit(request.user, request.amount, Transaction.ADMIN_ADJUST,
           ref=f'payout:{request.id}', note='Возврат отклонённой заявки на вывод')
    request.status = PayoutRequest.REJECTED
    request.decided_by = decided_by
    request.save(update_fields=['status', 'decided_by', 'comment'])
    return request
