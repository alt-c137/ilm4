from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from apps.accounts.audit import log_action

from .choices import FAITH_QUESTIONS, FAITH_RED_FLAGS
from .models import NikahInterest, NikahMatch, NikahProfile


class RedFlagFilter(admin.SimpleListFilter):
    title = 'закрытые ответы'
    parameter_name = 'flag'

    def lookups(self, request, model_admin):
        return [('1', 'Есть тревожные ответы')]

    def queryset(self, request, queryset):
        if self.value() == '1':
            ids = [p.pk for p in queryset if any(p.faith_answers.get(k) == v for k, v in FAITH_RED_FLAGS.items())]
            return queryset.filter(pk__in=ids)
        return queryset


@admin.register(NikahProfile)
class NikahProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'gender', 'age', 'city', 'country', 'aqida', 'status', 'verified',
                    'has_photo', 'flags', 'created_at')
    list_filter = ('status', 'verified', 'gender', 'aqida', 'madhhab', RedFlagFilter)
    search_fields = ('user__email', 'name', 'city', 'country', 'about', 'manhaj_text')
    readonly_fields = ('faith_table', 'photo_link', 'agreed_at', 'created_at', 'updated_at')
    actions = ('approve', 'reject')
    fieldsets = (
        (None, {'fields': ('user', 'status', 'verified', 'is_active', 'boosted_until', 'premium_until',
                           'referred_by')}),
        ('Анкета', {'fields': ('gender', 'name', 'age', ('age_from', 'age_to'), ('country', 'city', 'nationality'),
                               ('height', 'weight'), ('marital', 'wife_number', 'polygyny'))}),
        ('Религия', {'fields': (('madhhab', 'aqida'), ('prayer', 'quran'), 'where_allah', 'look', 'manhaj_text')}),
        ('Семья', {'fields': (('children_want', 'children_accept'), ('ready_when', 'relocation'))}),
        ('Тексты', {'fields': ('about', 'partner_expectations')}),
        ('Фото и закрытые ответы', {'fields': ('photo_mode', 'photo_link', 'faith_table', 'agreed_at')}),
    )

    @admin.display(description='тревожные')
    def flags(self, obj):
        bad = [k for k, v in FAITH_RED_FLAGS.items() if obj.faith_answers.get(k) == v]
        return format_html('<b style="color:#c0392b">{}</b>', ', '.join(bad)) if bad else '—'

    @admin.display(description='закрытые ответы')
    def faith_table(self, obj):
        rows = format_html_join('', '<tr><td>{}</td><td><b>{}</b></td></tr>', (
            (q, {'yes': opts[0], 'no': opts[1]}.get(obj.faith_answers.get(key), '—'))
            for key, q, opts in FAITH_QUESTIONS))
        return format_html('<table>{}</table>', rows)

    @admin.display(description='фото')
    def photo_link(self, obj):
        if not obj.has_photo:
            return 'нет'
        return format_html('<a href="{}" target="_blank">Посмотреть для модерации (запишется в журнал)</a>',
                           reverse('nikah:admin_photo', args=[obj.pk]))

    @admin.action(description='Одобрить')
    def approve(self, request, queryset):
        from .bot import approve
        for p in queryset:
            approve(p)          # + уведомление и бонус пригласившему
        log_action(request, 'Одобрены анкеты никаха', f'{queryset.count()} шт.')

    @admin.action(description='Отклонить')
    def reject(self, request, queryset):
        from .bot import reject
        for p in queryset:
            reject(p)
        log_action(request, 'Отклонены анкеты никаха', f'{queryset.count()} шт.')


@admin.register(NikahMatch)
class NikahMatchAdmin(admin.ModelAdmin):
    list_display = ('sister', 'brother', 'stage', 'sister_ok', 'brother_ok', 'created_at')
    list_filter = ('stage',)
    raw_id_fields = ('sister', 'brother', 'thread')


@admin.register(NikahInterest)
class NikahInterestAdmin(admin.ModelAdmin):
    list_display = ('from_profile', 'to_profile', 'created_at')
    raw_id_fields = ('from_profile', 'to_profile')
