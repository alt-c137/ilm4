from django.contrib import admin, messages

from . import services
from .models import TopUp


@admin.register(TopUp)
class TopUpAdmin(admin.ModelAdmin):
    list_display = ('pk', 'user', 'amount', 'provider', 'status', 'created_at', 'paid_at')
    list_filter = ('status', 'provider')
    search_fields = ('user__email', 'external_id')
    readonly_fields = ('user', 'amount', 'provider', 'status', 'external_id', 'created_at', 'paid_at')
    actions = ('confirm_paid',)

    @admin.action(description='Подтвердить оплату и зачислить на баланс')
    def confirm_paid(self, request, queryset):
        n = sum(1 for t in queryset if services.mark_paid(t))
        messages.success(request, f'Зачислено пополнений: {n}')
