from django.contrib import admin

from apps.accounts.audit import log_action
from apps.core.models import Moderation

from .models import HalalPlace, PlaceConfirmation


@admin.register(HalalPlace)
class HalalPlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'city', 'status', 'platform_verified', 'owner', 'created_at')
    list_editable = ('platform_verified',)
    list_filter = ('status', 'platform_verified', 'category', 'city')
    search_fields = ('name', 'city', 'address', 'affiliation')
    actions = ('approve', 'reject')
    fieldsets = (
        (None, {'fields': ('name', 'category', 'status', 'platform_verified', 'owner')}),
        ('Где', {'fields': ('city', 'address', 'lat', 'lon')}),
        ('Контакты', {'fields': ('phone', 'url', 'description', 'photo')}),
        ('Мечеть (если категория «Мечеть»)', {'fields': (
            'branch', 'madhhab', 'manhaj', 'kind', 'affiliation', 'imam', 'khutba_lang',
            ('has_jumua', 'has_women', 'has_wudu', 'has_parking', 'accessible'))}),
    )

    @admin.action(description='Одобрить (опубликовать)')
    def approve(self, request, queryset):
        queryset.update(status=Moderation.APPROVED)
        log_action(request, 'Одобрены халяль-места', f'{queryset.count()} шт.')

    @admin.action(description='Отклонить')
    def reject(self, request, queryset):
        queryset.update(status=Moderation.REJECTED)
        log_action(request, 'Отклонены халяль-места', f'{queryset.count()} шт.')


@admin.register(PlaceConfirmation)
class PlaceConfirmationAdmin(admin.ModelAdmin):
    list_display = ('place', 'user', 'is_correct', 'note', 'suggestion', 'resolved', 'created_at')
    list_filter = ('is_correct', 'resolved')
    list_editable = ('resolved',)
    search_fields = ('place__name', 'note')
    actions = ('apply_suggestion',)

    FIELDS = ('branch', 'madhhab', 'manhaj', 'kind')

    @admin.display(description='предлагают')
    def suggestion(self, obj):
        return ' · '.join(getattr(obj, f'get_suggested_{f}_display')() for f in self.FIELDS
                          if getattr(obj, f'suggested_{f}')) or '—'

    @admin.action(description='Применить предложенные поля к мечети и закрыть')
    def apply_suggestion(self, request, queryset):
        n = 0
        for c in queryset.select_related('place'):
            changed = [f for f in self.FIELDS if getattr(c, f'suggested_{f}')]
            for f in changed:
                setattr(c.place, f, getattr(c, f'suggested_{f}'))
            if changed:
                c.place.save(update_fields=changed)
                n += 1
            c.resolved = True
            c.save(update_fields=['resolved'])
        log_action(request, 'Применены уточнения мечетей', f'{n} шт.')
        self.message_user(request, f'Применено: {n}')
