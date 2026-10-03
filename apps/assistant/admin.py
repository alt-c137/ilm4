from django.contrib import admin

from .models import AssistantPlan


@admin.register(AssistantPlan)
class AssistantPlanAdmin(admin.ModelAdmin):
    """Подписка на помощника: «без лимита до…» — пока выдаётся вручную, с оплатой из кошелька будет продлеваться сама."""
    list_display = ('user', 'until', 'extra_daily', 'note')
    raw_id_fields = ('user',)
    search_fields = ('user__email', 'user__handle', 'note')
