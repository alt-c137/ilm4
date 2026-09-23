"""Рейтинг объекта и права на отзыв."""
from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Count

from .models import REVIEWABLE, Review


def ct_key(obj) -> str:
    ct = ContentType.objects.get_for_model(obj)
    return f'{ct.app_label}.{ct.model}'


def owner_of(obj):
    """Кого нельзя пускать оценивать самого себя."""
    if obj.__class__.__name__ == 'User':
        return obj
    return getattr(obj, 'owner', None)


def reviews_for(obj):
    ct = ContentType.objects.get_for_model(obj)
    return Review.objects.filter(content_type=ct, object_id=obj.pk, is_hidden=False).select_related('author')


def is_rated(obj) -> bool:
    """Ставятся ли звёзды. Мечети — без оценок, только сообщения."""
    return getattr(obj, 'category', None) != 'mosque'


def summary(obj) -> dict:
    """{'avg': 4.7, 'count': 12, …} — только отзывы с оценкой."""
    agg = reviews_for(obj).filter(rating__isnull=False).aggregate(avg=Avg('rating'), count=Count('id'))
    avg = round(agg['avg'] or 0, 1)
    return {'avg': avg, 'count': agg['count'] or 0, 'full': int(avg), 'half': (avg - int(avg)) >= 0.5}


def can_review(user, obj) -> bool:
    """Оценивать может любой вошедший — кроме владельца объекта (себя не оцениваем)."""
    if not user.is_authenticated or ct_key(obj) not in REVIEWABLE:
        return False
    owner = owner_of(obj)
    return owner is None or owner.pk != user.pk
