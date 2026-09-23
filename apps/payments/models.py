"""Пополнение баланса через платёжного провайдера (карта / крипта).

Деньги зачисляются на баланс ТОЛЬКО после подтверждения оплаты провайдером
(вебхук) или админом — через apps.wallet.services.credit. Повторное
подтверждение ничего не зачисляет (status проверяется под блокировкой).
"""
from django.conf import settings
from django.db import models


class TopUp(models.Model):
    PENDING, PAID, FAILED, CANCELLED = 'pending', 'paid', 'failed', 'cancelled'
    STATUSES = [(PENDING, 'Ожидает оплаты'), (PAID, 'Оплачено, зачислено'), (FAILED, 'Ошибка'), (CANCELLED, 'Отменено')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='topups')
    amount = models.DecimalField('сумма, сум', max_digits=14, decimal_places=0)
    provider = models.CharField('способ', max_length=20)
    status = models.CharField('статус', max_length=10, choices=STATUSES, default=PENDING, db_index=True)
    external_id = models.CharField('id у провайдера', max_length=120, blank=True, db_index=True)
    created_at = models.DateTimeField('создано', auto_now_add=True)
    paid_at = models.DateTimeField('оплачено', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'пополнение'
        verbose_name_plural = 'пополнения'

    def __str__(self):
        return f'#{self.pk} {self.user} {self.amount} ({self.get_status_display()})'
