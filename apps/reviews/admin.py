from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'rating', 'author', 'is_hidden', 'created_at')
    list_filter = ('rating', 'is_hidden', 'content_type')
    list_editable = ('is_hidden',)
    search_fields = ('text', 'author__email', 'author__username')
    readonly_fields = ('content_type', 'object_id', 'author', 'created_at', 'updated_at')
