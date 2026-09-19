from django.contrib import admin

from apps.accounts.audit import log_action
from apps.core.models import Moderation

from .models import Ride


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ('from_city', 'to_city', 'type', 'ride_date', 'status', 'created_at')
    list_filter = ('status', 'type')
    search_fields = ('from_city', 'to_city', 'description')
    actions = ('approve',)

    @admin.action(description='Одобрить')
    def approve(self, request, queryset):
        queryset.update(status=Moderation.APPROVED)
        log_action(request, 'Одобрены перевозки', f'{queryset.count()} шт.')
