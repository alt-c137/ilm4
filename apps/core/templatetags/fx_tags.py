"""{% get_fx as fx %} — курсы для карточки «Сегодня» (см. apps/core/fx.py)."""
from django import template

from .. import fx as fx_service

register = template.Library()


@register.simple_tag
def get_fx() -> dict:
    return fx_service.get_rates()
