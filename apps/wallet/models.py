
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _lazy


class Wallet(models.Model):
    """Баланс пользователя. Меняется ТОЛЬКО через apps.wallet.services (§5)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='wallet', verbose_name='пользователь')
    balance = models.DecimalField('баланс, сум', max_digits=14, decimal_places=0, default=0)
    updated_at = models.DateTimeField('обновлён', auto_now=True)

    class Meta:
        verbose_name = 'кошелёк'
        verbose_name_plural = 'кошельки'

    def __str__(self):
        return f'{self.user} — {self.balance}'


class Transaction(models.Model):
    """Журнал транзакций: append-only, строки только добавляются (§5).

    amount всегда положительный; вид операции определяет знак движения денег.
    balance_after — снимок баланса сразу после операции (для истории).
    """

    TOPUP = 'topup'                # пополнение
    EARN = 'earn'                  # заработок (продажа и т.п.)
    PURCHASE = 'purchase'          # платное действие (никах, буст, публикация)
    PAYOUT = 'payout'              # вывод средств
    ESCROW_HOLD = 'escrow_hold'    # заморозка в эскроу
    ESCROW_RELEASE = 'escrow_rel'  # эскроу выплачен продавцу
    ESCROW_REFUND = 'escrow_ref'   # эскроу возвращён покупателю
    ADMIN_ADJUST = 'admin_adjust'  # корректировка админом
    KINDS = [
        (TOPUP, _lazy('Пополнение')), (EARN, _lazy('Зачисление')),
        (PURCHASE, _lazy('Списание')), (PAYOUT, _lazy('Вывод')),
        (ESCROW_HOLD, _lazy('Эскроу: заморозка')), (ESCROW_RELEASE, _lazy('Эскроу: выплата')),
        (ESCROW_REFUND, _lazy('Эскроу: возврат')), (ADMIN_ADJUST, _lazy('Корректировка')),
    ]
    DEBIT_KINDS = {PURCHASE, PAYOUT, ESCROW_HOLD}   # уменьшают баланс
    CREDIT_KINDS = {TOPUP, EARN, ESCROW_RELEASE, ESCROW_REFUND, ADMIN_ADJUST}

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='transactions', verbose_name='пользователь')
    amount = models.DecimalField('сумма, сум', max_digits=14, decimal_places=0)
    kind = models.CharField('вид', max_length=12, choices=KINDS)
    ref = models.CharField('объект (модуль:действие:id)', max_length=120, blank=True)
    note = models.CharField('заметка', max_length=200, blank=True)
    balance_after = models.DecimalField('баланс после', max_digits=14, decimal_places=0)
    created_at = models.DateTimeField('создано', auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'транзакция'
        verbose_name_plural = 'транзакции'

    def __str__(self):
        sign = '−' if self.kind in self.DEBIT_KINDS else '+'
        return f'{self.user}: {sign}{self.amount} ({self.get_kind_display()})'

    @property
    def is_debit(self) -> bool:
        """Уменьшает ли баланс (для шаблонов истории)."""
        return self.kind in self.DEBIT_KINDS


class PayoutRequest(models.Model):
    """Заявка на вывод средств. Обрабатывает админ вручную (на старте)."""

    PENDING, DONE, REJECTED = 'pending', 'done', 'rejected'
    STATUSES = [(PENDING, _lazy('Ожидает')), (DONE, _lazy('Выполнена')), (REJECTED, _lazy('Отклонена'))]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='payout_requests', verbose_name='пользователь')
    amount = models.DecimalField('сумма, сум', max_digits=14, decimal_places=0)
    status = models.CharField('статус', max_length=10, choices=STATUSES, default=PENDING)
    comment = models.CharField('комментарий', max_length=300, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='payout_decisions',
                                   verbose_name='кто решил')
    created_at = models.DateTimeField('создано', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'заявка на вывод'
        verbose_name_plural = 'заявки на вывод'

    def __str__(self):
        return f'{self.user}: {self.amount} ({self.get_status_display()})'


class EscrowDeal(models.Model):
    """Сделка с гарантией (§5): платформа держит деньги до решения.

    hold → released (получил продавец) | refunded (вернулся покупателю).
    Создаётся через services.escrow_hold — деньги списываются сразу.
    """

    HOLD, RELEASED, REFUNDED = 'hold', 'released', 'refunded'
    STATUSES = [(HOLD, _lazy('Деньги заморожены')), (RELEASED, _lazy('Выплачена продавцу')),
                (REFUNDED, _lazy('Возвращена покупателю'))]

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='escrow_buys', verbose_name='покупатель')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='escrow_sells', verbose_name='продавец')
    amount = models.DecimalField('сумма, сум', max_digits=14, decimal_places=0)
    fee = models.DecimalField('комиссия платформы, сум', max_digits=14, decimal_places=0, default=0)
    status = models.CharField('статус', max_length=10, choices=STATUSES, default=HOLD)
    ref = models.CharField('объект', max_length=120, blank=True)
    note = models.CharField('описание спора/решения', max_length=300, blank=True)
    created_at = models.DateTimeField('создано', auto_now_add=True)
    resolved_at = models.DateTimeField('решено', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'эскроу-сделка'
        verbose_name_plural = 'эскроу-сделки'

    def __str__(self):
        return f'{self.buyer} → {self.seller}: {self.amount} ({self.get_status_display()})'
