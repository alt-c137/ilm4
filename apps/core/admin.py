from django.contrib import admin
from solo.admin import SingletonModelAdmin

from .models import Banner, ModuleConfig, Notification, Rate, SiteSettings, SocialLink, Theme


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


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'subtitle', 'cta_url', 'duration_seconds', 'order', 'is_active')
    list_editable = ('order', 'is_active', 'duration_seconds')


admin.site.register(Rate)
admin.site.register(SiteSettings, SingletonModelAdmin)


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ('label', 'kind', 'url', 'order', 'is_active')
    list_editable = ('order', 'is_active')
