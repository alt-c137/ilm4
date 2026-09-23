from django.contrib import admin

from apps.accounts.audit import log_action
from apps.core.models import Moderation

from .models import HalalPlace, PlaceConfirmation


@admin.register(HalalPlace)
class HalalPlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'city', 'status', 'platform_verified', 'owner', 'created_at')
    list_editable = ('platform_verified',)
    list_filter = ('status', 'platform_verified', 'category', 'city')
    search_fields = ('name', 'city', 'address', 'affiliation')
    actions = ('approve', 'reject')
    fieldsets = (
        (None, {'fields': ('name', 'category', 'status', 'platform_verified', 'owner')}),
        ('Где', {'fields': ('city', 'address', 'lat', 'lon')}),
        ('Контакты', {'fields': ('phone', 'url', 'description', 'photo')}),
        ('Мечеть (если категория «Мечеть»)', {'fields': (
            'branch', 'madhhab', 'affiliation', 'imam', 'khutba_lang',
            ('has_jumua', 'has_women', 'has_wudu', 'has_parking', 'accessible'))}),
    )

    @admin.action(description='Одобрить (опубликовать)')
    def approve(self, request, queryset):
        queryset.update(status=Moderation.APPROVED)
        log_action(request, 'Одобрены халяль-места', f'{queryset.count()} шт.')

    @admin.action(description='Отклонить')
    def reject(self, request, queryset):
        queryset.update(status=Moderation.REJECTED)
        log_action(request, 'Отклонены халяль-места', f'{queryset.count()} шт.')


@admin.register(PlaceConfirmation)
class PlaceConfirmationAdmin(admin.ModelAdmin):
    list_display = ('place', 'user', 'is_correct', 'note', 'resolved', 'created_at')
    list_filter = ('is_correct', 'resolved')
    list_editable = ('resolved',)
    search_fields = ('place__name', 'note')
