from django.contrib import admin

from apps.accounts.audit import log_action
from apps.core.models import Moderation
from apps.core.signals import set_status

from .models import Book, BookPurchase


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'price', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('title', 'author')
    actions = ('approve',)

    @admin.action(description='Одобрить')
    def approve(self, request, queryset):
        set_status(queryset, Moderation.APPROVED)
        log_action(request, 'Одобрены книги', f'{queryset.count()} шт.')


@admin.register(BookPurchase)
class BookPurchaseAdmin(admin.ModelAdmin):
    list_display = ('book', 'user', 'created_at')
