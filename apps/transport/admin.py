from django.contrib import admin

from apps.accounts.audit import log_action
from apps.core.models import Moderation
from apps.core.signals import set_status

from .models import Ride, Trip, TripRequest


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ('from_city', 'to_city', 'type', 'ride_date', 'status', 'created_at')
    list_filter = ('status', 'type')
    search_fields = ('from_city', 'to_city', 'description')
    actions = ('approve',)

    @admin.action(description='Одобрить')
    def approve(self, request, queryset):
        set_status(queryset, Moderation.APPROVED)
        log_action(request, 'Одобрены перевозки', f'{queryset.count()} шт.')


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('from_city', 'to_city', 'departs_at', 'role', 'seats', 'price', 'currency', 'status', 'owner')
    list_filter = ('status', 'role', 'audience')
    search_fields = ('from_city', 'to_city', 'via', 'comment')
    raw_id_fields = ('owner',)
    actions = ('approve',)

    @admin.action(description='Одобрить')
    def approve(self, request, queryset):
        set_status(queryset, Moderation.APPROVED)
        log_action(request, 'Одобрены поездки (попутчики)', f'{queryset.count()} шт.')


@admin.register(TripRequest)
class TripRequestAdmin(admin.ModelAdmin):
    list_display = ('trip', 'user', 'seats', 'status', 'created_at')
    list_filter = ('status',)
    raw_id_fields = ('trip', 'user')
