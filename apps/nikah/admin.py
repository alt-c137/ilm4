from django.contrib import admin

from apps.accounts.audit import log_action
from apps.core.models import Moderation

from .models import NikahContact, NikahProfile


@admin.register(NikahProfile)
class NikahProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'gender', 'age', 'city', 'status', 'is_boosted', 'created_at')
    list_filter = ('status', 'gender')
    search_fields = ('user__email', 'city', 'about')
    actions = ('approve', 'reject')

    @admin.action(description='Одобрить')
    def approve(self, request, queryset):
        queryset.update(status=Moderation.APPROVED)
        log_action(request, 'Одобрены анкеты никаха', f'{queryset.count()} шт.')

    @admin.action(description='Отклонить')
    def reject(self, request, queryset):
        queryset.update(status=Moderation.REJECTED)


@admin.register(NikahContact)
class NikahContactAdmin(admin.ModelAdmin):
    list_display = ('from_user', 'to_profile', 'created_at')
