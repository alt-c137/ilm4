from django.contrib import admin

from apps.accounts.audit import log_action
from apps.core.models import Moderation

from .models import Reply, Topic


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('title', 'body')
    actions = ('approve', 'reject')

    @admin.action(description='Одобрить')
    def approve(self, request, queryset):
        queryset.update(status=Moderation.APPROVED)
        log_action(request, 'Одобрены темы форума', f'{queryset.count()} шт.')

    @admin.action(description='Отклонить')
    def reject(self, request, queryset):
        queryset.update(status=Moderation.REJECTED)


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ('topic', 'author', 'created_at')
    search_fields = ('body',)
