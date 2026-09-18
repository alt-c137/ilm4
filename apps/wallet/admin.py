
from django.contrib import admin

from apps.accounts.audit import log_action

from . import services
from .models import EscrowDeal, PayoutRequest, Transaction, Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__email', 'user__username')

    def has_add_permission(self, request):
        return False  # кошельки создают сервисы

    def has_change_permission(self, request, obj=None):
        return False  # баланс меняют только сервисы


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'kind', 'amount', 'balance_after', 'ref', 'created_at')
    list_filter = ('kind',)
    search_fields = ('user__email', 'ref')
    date_hierarchy = 'created_at'

    def has_change_permission(self, request, obj=None):
        return False  # журнал append-only

    def has_delete_permission(self, request, obj=None):
        return request.user.is_super_admin


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'status', 'created_at', 'decided_by')
    list_filter = ('status',)
    actions = ('mark_done', 'reject',)

    @admin.action(description='Отметить выполненной (деньги отправлены)')
    def mark_done(self, request, queryset):
        for obj in queryset.filter(status=PayoutRequest.PENDING):
            obj.status = PayoutRequest.DONE
            obj.decided_by = request.user
            obj.save(update_fields=['status', 'decided_by'])
            log_action(request, 'Заявка на вывод выполнена', f'payout:{obj.id}')

    @admin.action(description='Отклонить (вернуть на баланс)')
    def reject(self, request, queryset):
        for obj in queryset.filter(status=PayoutRequest.PENDING):
            services.reject_payout(obj, request.user)
            log_action(request, 'Заявка на вывод отклонена', f'payout:{obj.id}')


@admin.register(EscrowDeal)
class EscrowDealAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'seller', 'amount', 'status', 'ref', 'created_at')
    list_filter = ('status',)
    actions = ('release', 'refund',)

    @admin.action(description='Выплатить продавцу')
    def release(self, request, queryset):
        for deal in queryset.filter(status=EscrowDeal.HOLD):
            services.escrow_release(deal, decided_by=request.user)
            log_action(request, 'Эскроу выплачен продавцу', f'escrow:{deal.id}')

    @admin.action(description='Вернуть покупателю')
    def refund(self, request, queryset):
        for deal in queryset.filter(status=EscrowDeal.HOLD):
            services.escrow_refund(deal, decided_by=request.user)
            log_action(request, 'Эскроу возвращён покупателю', f'escrow:{deal.id}')

    def has_add_permission(self, request):
        return False  # сделки создают модули через services

    def has_delete_permission(self, request, obj=None):
        return False  # денежная история не удаляется
