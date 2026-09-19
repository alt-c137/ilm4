from django.contrib import admin

from .models import Org


@admin.register(Org)
class OrgAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'country', 'city', 'phones', 'updated_at')
    list_filter = ('kind', 'country')
    search_fields = ('name', 'city', 'address', 'phones')
    fieldsets = (
        ('Где', {'fields': ('country', 'city', 'address')}),
        ('Что', {'fields': ('name', 'kind', 'website')}),
        ('Контакты', {'fields': ('phones', 'notes')}),
    )
