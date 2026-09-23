from django.contrib import admin, messages

from . import services
from .models import Order, OrderEvent


class EventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ('actor', 'action', 'note', 'created_at')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('pk', 'title', 'client', 'provider', 'amount', 'status', 'created_at')
    list_filter = ('status', 'kind')
    search_fields = ('title', 'client__email', 'provider__email')
    readonly_fields = ('client', 'provider', 'amount', 'fee_percent', 'escrow', 'status', 'funded_at',
                       'delivered_at', 'closed_at', 'dispute_reason')
    inlines = [EventInline]
    actions = ('resolve_provider', 'resolve_refund')

    @admin.action(description='Спор: выплатить исполнителю')
    def resolve_provider(self, request, queryset):
        self._resolve(request, queryset, True)

    @admin.action(description='Спор: вернуть деньги заказчику')
    def resolve_refund(self, request, queryset):
        self._resolve(request, queryset, False)

    def _resolve(self, request, queryset, to_provider):
        done = 0
        for order in queryset:
            try:
                services.resolve(order, request.user, to_provider, note='решение модератора')
                done += 1
            except services.DealError as exc:
                messages.warning(request, f'#{order.pk}: {exc}')
        messages.success(request, f'Решено споров: {done}')
