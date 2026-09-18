from django.contrib import admin

from .models import NewsPost


@admin.register(NewsPost)
class NewsPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_pinned', 'created_at')
    list_editable = ('is_pinned',)
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'body')
