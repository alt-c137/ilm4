from django.contrib import admin

from .models import ApiToken, PushDevice


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    """Входы в приложении. Удалить строку = выкинуть телефон из аккаунта."""
    list_display = ('user', 'name', 'created_at', 'last_used_at')
    search_fields = ('user__email', 'user__username', 'name')
    readonly_fields = ('user', 'name', 'created_at', 'last_used_at')

    def has_add_permission(self, request):
        return False


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'platform', 'updated_at')
    search_fields = ('user__email',)
    readonly_fields = ('user', 'token', 'platform', 'updated_at')

    def has_add_permission(self, request):
        return False
