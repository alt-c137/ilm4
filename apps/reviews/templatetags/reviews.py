"""{% rating_badge obj %} — «★ 4.8 · 12 отзывов»; {% reviews_block obj %} — список и форма;
{% verified_badge obj %} — «Проверено ilm4» / «Не проверено» с пояснением."""
from django import template
from django.contrib.contenttypes.models import ContentType

from ..services import can_review, is_rated, owner_of, reviews_for, summary

register = template.Library()


@register.inclusion_tag('reviews/_badge.html')
def rating_badge(obj, compact=False):
    return {'s': summary(obj), 'compact': compact}


@register.inclusion_tag('reviews/_block.html', takes_context=True)
def reviews_block(context, obj, title='Отзывы'):
    request = context['request']
    user = request.user
    items = list(reviews_for(obj)[:30])
    mine = next((r for r in items if user.is_authenticated and r.author_id == user.pk), None)
    owner = owner_of(obj)
    return {
        'obj': obj, 'title': title, 'rated': is_rated(obj), 'items': items, 's': summary(obj), 'mine': mine,
        'can_review': can_review(user, obj), 'is_owner': bool(owner and user.is_authenticated and owner.pk == user.pk),
        'ct_id': ContentType.objects.get_for_model(obj).pk, 'request': request, 'user': user,
        'csrf_token': context.get('csrf_token'),
    }


@register.inclusion_tag('reviews/_verified.html')
def verified_badge(obj):
    return {'ok': bool(getattr(obj, 'platform_verified', False))}
