"""{% report_button obj %} — кнопка «Пожаловаться» для любой публикации, анкеты или человека."""
from django import template
from django.contrib.contenttypes.models import ContentType

from apps.core.models import Report

register = template.Library()


@register.inclusion_tag('includes/report.html', takes_context=True)
def report_button(context, obj, label='', thread=None, masked=False):
    """masked — собеседник в чате под «маской»: в форму не кладём номер его аккаунта, сервер найдёт его по чату."""
    owner = getattr(obj, 'owner', None) or getattr(obj, 'author', None) or getattr(obj, 'user', None)
    if obj._meta.label_lower == 'accounts.user':
        owner = obj
    hide = bool(masked and thread)
    return {'user': context.get('user'), 'request': context.get('request'), 'owner': owner, 'label': label,
            'ct_id': 0 if hide else ContentType.objects.get_for_model(obj).pk, 'obj_id': 0 if hide else obj.pk,
            'by_thread': hide, 'reasons': Report.REASONS, 'csrf_token': context.get('csrf_token'), 'thread': thread}
