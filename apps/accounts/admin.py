from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AuditLog, BannedIdentity, RegistrationField, SocialLink, User


class SocialLinkInline(admin.TabularInline):
    model = SocialLink
    extra = 0
    fields = ('kind', 'value', 'privacy')


@admin.register(User)
class Ilm4UserAdmin(UserAdmin):
    inlines = [SocialLinkInline]
    readonly_fields = ('last_seen_at',)
    list_display = ('username', 'email', 'handle', 'role', 'phone_ok', 'platform_verified', 'is_staff', 'is_active')
    list_filter = ('role', 'platform_verified', 'is_staff', 'is_active',
                   ('phone_verified_at', admin.EmptyFieldListFilter))
    search_fields = UserAdmin.search_fields + ('phone', 'telegram_username', 'handle', 'nickname')
    fieldsets = UserAdmin.fieldsets + (
        ('Профиль ilm4', {'fields': ('nickname', 'handle', 'bio', 'city', 'avatar', 'role', 'platform_verified', 'theme')}),
        ('Приватность', {'fields': ('phone_privacy', 'findable_by_phone', 'seen_privacy', 'last_seen_at')}),
        ('Номер и Telegram', {'fields': ('phone', 'phone_verified_at', 'telegram_id', 'telegram_username')}),
    )

    actions = ('ban_users', 'unban_users')

    @admin.display(description='номер', boolean=True, ordering='phone_verified_at')
    def phone_ok(self, obj):
        return obj.phone_verified

    @admin.action(description='Заблокировать (номер и Telegram — в чёрный список, публикации снять)')
    def ban_users(self, request, queryset):
        from .bans import ban, can_ban
        n = 0
        for u in queryset:
            if can_ban(request.user, u):
                ban(u, request.user, 'из админки')
                n += 1
        self.message_user(request, f'Заблокировано: {n}. Сотрудников и себя заблокировать нельзя.')

    @admin.action(description='Разблокировать (и убрать из чёрного списка)')
    def unban_users(self, request, queryset):
        from .bans import unban
        for u in queryset:
            unban(u, request.user)
        self.message_user(request, f'Разблокировано: {queryset.count()}.')
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


@admin.register(BannedIdentity)
class BannedIdentityAdmin(admin.ModelAdmin):
    """Чёрный список. Удалить запись = снова разрешить этот номер / Telegram."""

    list_display = ('kind', 'user', 'reason', 'created_by', 'created_at')
    list_filter = ('kind',)
    search_fields = ('user__email', 'user__username', 'reason')
    readonly_fields = ('kind', 'key', 'user', 'created_by', 'created_at')

    def has_add_permission(self, request):
        return False        # добавляется кнопкой «Заблокировать»
