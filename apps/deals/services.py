"""Переходы безопасной сделки. Каждый — атомарный, с проверкой роли и статуса.

Деньги двигает только кошелёк (apps.wallet.services): заморозка при оплате,
выплата исполнителю за вычетом комиссии при принятии, возврат при споре/отмене.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.wallet import services as wallet

from .models import Order, OrderEvent


class DealError(ValueError):
    pass


def settings_():
    from apps.core.models import SiteSettings
    return SiteSettings.get_solo()


def _log(order, actor, action, note=''):
    OrderEvent.objects.create(order=order, actor=actor, action=action, note=note[:500])


def _locked(order):
    return Order.objects.select_for_update().get(pk=order.pk)


def _need(order, user, role, *statuses):
    if role and order.role_of(user) != role:
        raise DealError('Это действие доступно другой стороне сделки')
    if statuses and order.status not in statuses:
        raise DealError(f'Нельзя в статусе «{order.get_status_display()}»')


@transaction.atomic
def create(client, provider, title, terms, amount, deadline=None, kind='freelance', thread=None) -> Order:
    st = settings_()
    if not st.escrow_enabled:
        raise DealError('Безопасная сделка пока не включена')
    if client.pk == provider.pk:
        raise DealError('Нельзя заказать у самого себя')
    try:
        amount = Decimal(str(amount)).quantize(Decimal(1))
    except (InvalidOperation, TypeError):
        raise DealError('Укажите сумму числом') from None
    if amount <= 0:
        raise DealError('Сумма должна быть больше нуля')
    if not title.strip() or not terms.strip():
        raise DealError('Опишите задачу и результат')
    order = Order.objects.create(client=client, provider=provider, title=title.strip()[:160],
                                 terms=terms.strip(), amount=amount, fee_percent=st.escrow_fee_percent,
                                 deadline=deadline, kind=kind, thread=thread)
    _log(order, client, 'offered')
    return order


@transaction.atomic
def accept(order, user):
    order = _locked(order)
    _need(order, user, 'provider', Order.OFFERED)
    order.status = Order.ACCEPTED
    order.save(update_fields=['status'])
    _log(order, user, 'accepted')
    return order


@transaction.atomic
def fund(order, user):
    """Заказчик оплачивает с баланса — деньги замораживаются на платформе."""
    order = _locked(order)
    _need(order, user, 'client', Order.ACCEPTED)
    deal = wallet.escrow_hold(order.client, order.provider, order.amount, ref=f'order:{order.pk}')
    order.escrow = deal
    order.status = Order.FUNDED
    order.funded_at = timezone.now()
    order.save(update_fields=['escrow', 'status', 'funded_at'])
    _log(order, user, 'funded')
    return order


@transaction.atomic
def deliver(order, user, note=''):
    order = _locked(order)
    _need(order, user, 'provider', Order.FUNDED)
    order.status = Order.DELIVERED
    order.delivered_at = timezone.now()
    order.save(update_fields=['status', 'delivered_at'])
    _log(order, user, 'delivered', note)
    return order


@transaction.atomic
def complete(order, user=None, auto=False):
    """Заказчик принял (или сработало автопринятие) — выплата исполнителю минус комиссия."""
    order = _locked(order)
    if not auto:
        _need(order, user, 'client', Order.DELIVERED)
    elif order.status != Order.DELIVERED:
        raise DealError('Автопринятие — только для сданной работы')
    wallet.escrow_release(order.escrow, fee=order.fee)
    order.status = Order.COMPLETED
    order.closed_at = timezone.now()
    order.save(update_fields=['status', 'closed_at'])
    _log(order, user, 'auto_completed' if auto else 'completed')
    return order


@transaction.atomic
def dispute(order, user, reason):
    order = _locked(order)
    if order.role_of(user) is None:
        raise DealError('Вы не участник сделки')
    _need(order, user, None, Order.FUNDED, Order.DELIVERED)
    if not reason.strip():
        raise DealError('Опишите, что пошло не так')
    order.status = Order.DISPUTED
    order.dispute_reason = reason.strip()
    order.save(update_fields=['status', 'dispute_reason'])
    _log(order, user, 'disputed', reason)
    return order


@transaction.atomic
def resolve(order, admin, to_provider: bool, note=''):
    """Решение модератора по спору: выплатить исполнителю или вернуть заказчику."""
    order = _locked(order)
    _need(order, admin, None, Order.DISPUTED)
    if to_provider:
        wallet.escrow_release(order.escrow, decided_by=admin, fee=order.fee)
        order.status = Order.COMPLETED
    else:
        wallet.escrow_refund(order.escrow, decided_by=admin)
        order.status = Order.REFUNDED
    order.closed_at = timezone.now()
    order.save(update_fields=['status', 'closed_at'])
    _log(order, admin, 'resolved_provider' if to_provider else 'resolved_refund', note)
    return order


@transaction.atomic
def cancel(order, user):
    """Отмена до оплаты — любой стороной; деньги ещё не списаны."""
    order = _locked(order)
    if order.role_of(user) is None:
        raise DealError('Вы не участник сделки')
    _need(order, user, None, Order.OFFERED, Order.ACCEPTED)
    order.status = Order.CANCELLED
    order.closed_at = timezone.now()
    order.save(update_fields=['status', 'closed_at'])
    _log(order, user, 'cancelled')
    return order


def release_due(now=None) -> int:
    """Автопринятие: работа сдана N дней назад, заказчик молчит — выплатить."""
    now = now or timezone.now()
    days = settings_().escrow_auto_release_days
    due = Order.objects.filter(status=Order.DELIVERED, delivered_at__lte=now - timedelta(days=days))
    n = 0
    for order in due:
        try:
            complete(order, auto=True)
            n += 1
        except DealError:
            pass
    return n
