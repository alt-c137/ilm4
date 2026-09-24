from django.contrib import admin

from apps.accounts.audit import log_action
from apps.core.models import Moderation
from apps.core.signals import set_status

from .models import Doctor


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'city', 'status', 'platform_verified', 'owner', 'created_at')
    list_editable = ('platform_verified',)
    list_filter = ('status', 'platform_verified', 'category', 'city')
    search_fields = ('name', 'city', 'clinic')
    actions = ('approve', 'reject')

    @admin.action(description='Одобрить (опубликовать)')
    def approve(self, request, queryset):
        set_status(queryset, Moderation.APPROVED)
        log_action(request, 'Одобрены врачи', f'{queryset.count()} шт.')

    @admin.action(description='Отклонить')
    def reject(self, request, queryset):
        set_status(queryset, Moderation.REJECTED)
        log_action(request, 'Отклонены врачи', f'{queryset.count()} шт.')
