from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AuditLog, RegistrationField, User


@admin.register(User)
class Ilm4UserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'phone_ok', 'platform_verified', 'is_staff', 'is_active')
    list_filter = ('role', 'platform_verified', 'is_staff', 'is_active',
                   ('phone_verified_at', admin.EmptyFieldListFilter))
    search_fields = UserAdmin.search_fields + ('phone', 'telegram_username')
    fieldsets = UserAdmin.fieldsets + (
        ('Профиль ilm4', {'fields': ('nickname', 'city', 'avatar', 'role', 'platform_verified', 'theme')}),
        ('Номер и Telegram', {'fields': ('phone', 'phone_verified_at', 'telegram_id', 'telegram_username')}),
    )

    @admin.display(description='номер', boolean=True, ordering='phone_verified_at')
    def phone_ok(self, obj):
        return obj.phone_verified
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Профиль ilm4', {'fields': ('email', 'role')}),
    )


@admin.register(RegistrationField)
class RegistrationFieldAdmin(admin.ModelAdmin):
    list_display = ('label', 'key', 'enabled', 'required', 'order')
    list_editable = ('enabled', 'required', 'order')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Журнал — только чтение: записи не правят и не удаляют из админки."""

    list_display = ('user', 'action', 'target', 'ip', 'created_at')
    list_filter = ('action',)
    search_fields = ('user__email', 'action', 'target')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_super_admin  # чистить журнал может только супер-админ
