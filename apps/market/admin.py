from django.contrib import admin

from apps.accounts.audit import log_action
from apps.core.models import Moderation
from apps.core.signals import set_status

from .models import Category, Listing


class ListingInline(admin.TabularInline):
    model = Listing
    extra = 0
    can_delete = False
    fields = ('title', 'city', 'price', 'status')
    readonly_fields = fields


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'icon')
    list_display_links = ('name',)
    list_editable = ('slug', 'order', 'icon')


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'city', 'price', 'currency', 'status',
                    'is_boosted', 'views', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'description', 'city', 'owner__email')
    actions = ('approve', 'reject')

    @admin.action(description='Одобрить (опубликовать)')
    def approve(self, request, queryset):
        set_status(queryset, Moderation.APPROVED)
        log_action(request, 'Одобрены объявления', f'{queryset.count()} шт.')

    @admin.action(description='Отклонить')
    def reject(self, request, queryset):
        set_status(queryset, Moderation.REJECTED)
        log_action(request, 'Отклонены объявления', f'{queryset.count()} шт.')
