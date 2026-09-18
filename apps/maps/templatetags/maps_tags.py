"""Тег блока главной: свежие халяль-места и врачи ({% recent_places as r %})."""
from django import template

from apps.core.models import Moderation

register = template.Library()


@register.simple_tag
def recent_places(limit: int = 4) -> dict:
    from apps.health.models import Doctor

    from ..models import HalalPlace

    places = list(HalalPlace.objects.filter(status=Moderation.APPROVED)[:limit])
    doctors = list(Doctor.objects.filter(status=Moderation.APPROVED)[:limit])
    return {'places': places, 'doctors': doctors, 'total': len(places) + len(doctors)}
