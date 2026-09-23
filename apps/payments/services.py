from django.db import transaction
from django.utils import timezone

from apps.wallet import services as wallet
from apps.wallet.models import Transaction

from .models import TopUp


@transaction.atomic
def mark_paid(topup: TopUp) -> bool:
    """Подтвердить оплату и зачислить на баланс. Повтор — без зачисления."""
    topup = TopUp.objects.select_for_update().get(pk=topup.pk)
    if topup.status == TopUp.PAID:
        return False
    wallet.credit(topup.user, topup.amount, Transaction.TOPUP, ref=f'topup:{topup.pk}',
                  note=f'Пополнение #{topup.pk} ({topup.provider})')
    topup.status = TopUp.PAID
    topup.paid_at = timezone.now()
    topup.save(update_fields=['status', 'paid_at'])
    return True
