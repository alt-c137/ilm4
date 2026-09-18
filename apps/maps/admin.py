from django.contrib import admin

from apps.accounts.audit import log_action
from apps.core.models import Moderation

from .models import HalalPlace


@admin.register(HalalPlace)
class HalalPlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'city', 'status', 'owner', 'created_at')
    list_filter = ('status', 'category', 'city')
    search_fields = ('name', 'city', 'address')
    actions = ('approve', 'reject')

    @admin.action(description='Одобрить (опубликовать)')
    def approve(self, request, queryset):
        queryset.update(status=Moderation.APPROVED)
        log_action(request, 'Одобрены халяль-места', f'{queryset.count()} шт.')

    @admin.action(description='Отклонить')
    def reject(self, request, queryset):
        queryset.update(status=Moderation.REJECTED)
        log_action(request, 'Отклонены халяль-места', f'{queryset.count()} шт.')
