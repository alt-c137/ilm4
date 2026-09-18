from django.contrib import admin

from apps.accounts.audit import log_action
from apps.core.models import Moderation

from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'city', 'status', 'created_at')
    list_filter = ('status', 'kind')
    actions = ('approve',)

    @admin.action(description='Одобрить')
    def approve(self, request, queryset):
        queryset.update(status=Moderation.APPROVED)
        log_action(request, 'Одобрены услуги', f'{queryset.count()} шт.')
