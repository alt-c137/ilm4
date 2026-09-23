"""Безопасная сделка: заказ с удержанием оплаты до сдачи работы.

offered → accepted → funded (деньги заморожены) → delivered → completed (выплата − комиссия)
                                  ↘ disputed → refunded | completed (решает модератор)
offered/accepted → cancelled
Деньги двигает только apps.wallet.services (escrow_hold / escrow_release / escrow_refund).
"""
from django.conf import settings
from django.db import models


class Order(models.Model):
    OFFERED, ACCEPTED, FUNDED, DELIVERED = 'offered', 'accepted', 'funded', 'delivered'
    COMPLETED, DISPUTED, REFUNDED, CANCELLED = 'completed', 'disputed', 'refunded', 'cancelled'
    STATUSES = [
        (OFFERED, 'Предложен'), (ACCEPTED, 'Принят исполнителем'), (FUNDED, 'Оплачен, деньги удержаны'),
        (DELIVERED, 'Работа сдана'), (COMPLETED, 'Завершён, выплачено'), (DISPUTED, 'Спор'),
        (REFUNDED, 'Деньги возвращены'), (CANCELLED, 'Отменён'),
    ]
    KINDS = [('freelance', 'Фриланс / услуга'), ('ad', 'Реклама'), ('transport', 'Перевозка'), ('other', 'Другое')]

    kind = models.CharField('вид', max_length=10, choices=KINDS, default='freelance')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders_placed',
                               verbose_name='заказчик')
    provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders_taken',
                                 verbose_name='исполнитель')
    title = models.CharField('что нужно сделать', max_length=160)
    terms = models.TextField('условия и результат', help_text='Что именно сдаётся, объём, формат, правки')
    amount = models.DecimalField('сумма, сум', max_digits=14, decimal_places=0)
    fee_percent = models.DecimalField('комиссия, %', max_digits=4, decimal_places=2)
    deadline = models.DateField('срок сдачи', null=True, blank=True)
    status = models.CharField('статус', max_length=10, choices=STATUSES, default=OFFERED, db_index=True)
    escrow = models.OneToOneField('wallet.EscrowDeal', null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='order', verbose_name='удержание')
    thread = models.ForeignKey('chat.Thread', null=True, blank=True, on_delete=models.SET_NULL, related_name='orders')
    dispute_reason = models.TextField('причина спора', blank=True)
    created_at = models.DateTimeField('создан', auto_now_add=True)
    funded_at = models.DateTimeField('оплачен', null=True, blank=True)
    delivered_at = models.DateTimeField('сдан', null=True, blank=True)
    closed_at = models.DateTimeField('закрыт', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'безопасная сделка'
        verbose_name_plural = 'безопасные сделки'

    def __str__(self):
        return f'#{self.pk} {self.title} ({self.get_status_display()})'

    @property
    def fee(self):
        from decimal import ROUND_HALF_UP, Decimal
        return (self.amount * self.fee_percent / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP)

    @property
    def payout(self):
        return self.amount - self.fee

    @property
    def is_open(self):
        return self.status not in (self.COMPLETED, self.REFUNDED, self.CANCELLED)

    def role_of(self, user):
        if user.pk == self.client_id:
            return 'client'
        if user.pk == self.provider_id:
            return 'provider'
        return None


class OrderEvent(models.Model):
    LABELS = {
        'offered': 'Заказ предложен', 'accepted': 'Исполнитель принял условия', 'funded': 'Оплачено, деньги удержаны',
        'delivered': 'Работа сдана', 'completed': 'Работа принята, выплачено', 'auto_completed': 'Автопринятие, выплачено',
        'disputed': 'Открыт спор', 'resolved_provider': 'Спор решён: выплата исполнителю',
        'resolved_refund': 'Спор решён: возврат заказчику', 'cancelled': 'Заказ отменён',
    }

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    action = models.CharField('действие', max_length=20)
    note = models.CharField('комментарий', max_length=500, blank=True)
    created_at = models.DateTimeField('когда', auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'событие сделки'
        verbose_name_plural = 'события сделок'

    @property
    def label(self):
        return self.LABELS.get(self.action, self.action)
