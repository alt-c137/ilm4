"""Тег блока главной: свежие вопросы форума ({% recent_topics as r %})."""
from django import template

from apps.core.models import Moderation

register = template.Library()


@register.simple_tag
def recent_topics(limit: int = 6):
    from ..models import Topic

    return (Topic.objects.filter(status=Moderation.APPROVED)
            .select_related('author')[:limit])
