"""{% report_button obj %} — кнопка «Пожаловаться» для любой публикации, анкеты или человека."""
from django import template
from django.contrib.contenttypes.models import ContentType

from apps.core.models import Report

register = template.Library()


@register.inclusion_tag('includes/report.html', takes_context=True)
def report_button(context, obj, label=''):
    owner = getattr(obj, 'owner', None) or getattr(obj, 'author', None) or getattr(obj, 'user', None)
    if obj._meta.label_lower == 'accounts.user':
        owner = obj
    return {'user': context.get('user'), 'request': context.get('request'), 'owner': owner, 'label': label,
            'ct_id': ContentType.objects.get_for_model(obj).pk, 'obj_id': obj.pk, 'reasons': Report.REASONS,
            'csrf_token': context.get('csrf_token')}
