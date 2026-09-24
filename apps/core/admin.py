from django.contrib import admin
from solo.admin import SingletonModelAdmin

from .models import Banner, Moderation, ModuleConfig, Notification, Rate, Report, SiteSettings, SocialLink, Theme


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


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'reason', 'object_link', 'reporter', 'status', 'same_count')
    list_filter = ('status', 'reason', 'content_type')
    list_editable = ('status',)
    readonly_fields = ('content_type', 'object_id', 'reporter', 'reason', 'text', 'created_at', 'object_link')
    actions = ('hide_objects', 'dismiss')

    @admin.display(description='на что')
    def object_link(self, obj):
        from django.urls import NoReverseMatch, reverse
        from django.utils.html import format_html
        try:
            url = reverse(f'admin:{obj.content_type.app_label}_{obj.content_type.model}_change', args=[obj.object_id])
        except NoReverseMatch:
            return f'{obj.content_type.model} #{obj.object_id}'
        return format_html('<a href="{}">{} #{}</a>', url, obj.content_type.model, obj.object_id)

    @admin.display(description='всего жалоб')
    def same_count(self, obj):
        return Report.objects.filter(content_type=obj.content_type, object_id=obj.object_id).count()

    @admin.action(description='Скрыть объекты (отклонить) и закрыть жалобы')
    def hide_objects(self, request, queryset):
        from .signals import set_status
        for r in queryset:
            model = r.content_type.model_class()
            if hasattr(model, 'status'):
                set_status(model.objects.filter(pk=r.object_id), Moderation.REJECTED)
            elif r.content_type.model == 'user':
                model.objects.filter(pk=r.object_id).update(is_active=False)
        queryset.update(status=Report.RESOLVED)

    @admin.action(description='Жалобы необоснованны — закрыть')
    def dismiss(self, request, queryset):
        queryset.update(status=Report.DISMISSED)
