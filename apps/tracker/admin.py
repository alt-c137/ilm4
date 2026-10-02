from django.contrib import admin

from .models import Board, Habit


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    """Общие трекеры. Личные привычки людей в админке не показываются — это их личное."""
    list_display = ('title', 'owner', 'compete', 'created_at')
    search_fields = ('title', 'owner__email')
    raw_id_fields = ('owner',)
    readonly_fields = ('invite_code',)


@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = ('title', 'board', 'owner', 'kind', 'archived')
    list_filter = ('kind', 'archived')
    search_fields = ('title',)
    raw_id_fields = ('owner', 'board')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(board__isnull=False)     # только привычки общих трекеров
