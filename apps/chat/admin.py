"""Админка мессенджера. Переписки здесь нет намеренно (docs/MESSENGER.md §2.2): модератор читает
диалог только по жалобе, со страницы модерации, и это пишется в журнал. В админке — только
группы и каналы как «вывески»: название, публичность, галочка «официальный», закрытие за нарушения."""
from django.contrib import admin

from .models import Room, Thread


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'handle', 'is_public', 'members_count', 'platform_verified', 'closed', 'owner', 'updated_at')
    list_filter = ('kind', 'is_public', 'platform_verified', 'closed')
    list_editable = ('platform_verified', 'closed')
    search_fields = ('title', 'handle', 'about')
    fields = ('kind', 'title', 'about', 'avatar', 'handle', 'is_public', 'only_admins_post', 'platform_verified', 'closed',
              'owner', 'members_count')
    readonly_fields = ('kind', 'owner', 'members_count')

    def get_queryset(self, request):
        return super().get_queryset(request).exclude(kind=Thread.DIRECT)      # личные диалоги в админке не показываем

    def has_add_permission(self, request):
        return False
