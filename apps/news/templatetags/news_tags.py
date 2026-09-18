"""Тег блока главной: последние новости ({% recent_news as r %})."""
from django import template

register = template.Library()


@register.simple_tag
def recent_news(limit: int = 3):
    from ..models import NewsPost

    return NewsPost.objects.all()[:limit]
