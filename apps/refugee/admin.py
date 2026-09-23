from django.contrib import admin

from .models import Org


@admin.register(Org)
class OrgAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'region', 'country', 'city', 'phones', 'updated_at')
    list_filter = ('kind', 'region', 'country')
    search_fields = ('name', 'city', 'address', 'phones')
    fieldsets = (
        ('Где', {'fields': ('region', 'country', 'city', 'address')}),
        ('Что', {'fields': ('name', 'kind', 'website')}),
        ('Контакты', {'fields': ('phones', 'notes')}),
    )
