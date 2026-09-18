from django.contrib import admin
from solo.admin import SingletonModelAdmin

from .models import ModuleConfig, Notification, SiteSettings, Theme


@admin.register(ModuleConfig)
class ModuleConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'status', 'order', 'in_grid')
    list_editable = ('status', 'order', 'in_grid')
    list_filter = ('status',)
    search_fields = ('name', 'key')


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ('name', 'accent', 'accent_d', 'accent_soft', 'order')
    list_editable = ('order',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'text', 'read', 'created_at')
    list_filter = ('read',)


admin.site.register(SiteSettings, SingletonModelAdmin)
