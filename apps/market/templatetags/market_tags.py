"""Тег блока главной: свежие объявления ({% recent_listings as r %})."""
from django import template

from apps.core.models import Moderation

register = template.Library()


@register.simple_tag
def recent_listings(limit: int = 4):
    from ..models import Listing

    return (Listing.objects.filter(status=Moderation.APPROVED, is_active=True)
            .select_related('category')[:limit])
