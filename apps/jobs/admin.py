from django.contrib import admin

from apps.accounts.audit import log_action
from apps.core.models import Moderation
from apps.core.signals import set_status

from .models import Vacancy, VacancyResponse


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'city', 'status', 'created_at')
    list_filter = ('status', 'city')
    search_fields = ('title', 'company')
    actions = ('approve',)

    @admin.action(description='Одобрить')
    def approve(self, request, queryset):
        set_status(queryset, Moderation.APPROVED)
        log_action(request, 'Одобрены вакансии', f'{queryset.count()} шт.')


@admin.register(VacancyResponse)
class VacancyResponseAdmin(admin.ModelAdmin):
    list_display = ('vacancy', 'user', 'created_at')
