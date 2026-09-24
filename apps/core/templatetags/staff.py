"""Панель модератора над публикацией: {% staff_bar obj %}.

Обычный посетитель её не видит. Сотрудник видит статус и кнопки
«Одобрить / Отклонить / Снять» прямо на странице — без захода в админку.
"""
from django import template
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def staff_bar(context, obj):
    request = context.get('request')
    if request is None or obj is None:
        return ''
    from apps.core import moderation
    if not moderation.can_moderate(request.user, type(obj)):
        return ''
    src = next((s for s in moderation.SOURCES if s.get_model() is type(obj)), None)
    if src is None:
        return ''
    meta = obj._meta
    try:
        admin_url = reverse(f'admin:{meta.app_label}_{meta.model_name}_change', args=[obj.pk])
    except NoReverseMatch:
        admin_url = ''
    return render_to_string('core/includes/staff_bar.html', {
        'obj': obj, 'key': src.key, 'status': getattr(obj, 'status', ''), 'admin_url': admin_url,
        'status_label': obj.get_status_display() if hasattr(obj, 'get_status_display') else '',
        'next': request.get_full_path(), 'request': request,
    }, request=request)


@register.simple_tag(takes_context=True)
def ilm_dashboard(context):
    """Сводка для главной админки: что ждёт решения и как растёт сайт."""
    from datetime import timedelta

    from django.contrib.auth import get_user_model
    from django.utils import timezone

    from apps.core import moderation
    from apps.core.models import Moderation, Report
    user = context['request'].user
    nikah = moderation.BY_KEY['nikah'].get_model()
    pubs = sum(s.get_model().objects.filter(status=Moderation.PENDING).count()
               for s in moderation.SOURCES if s.key != 'nikah')
    User = get_user_model()
    week = timezone.now() - timedelta(days=7)
    return {
        'nikah': nikah.objects.filter(status=Moderation.PENDING).count(),
        'pubs': pubs,
        'reports': Report.objects.filter(status=Report.NEW).values('content_type', 'object_id').distinct().count(),
        'users': User.objects.filter(is_active=True).count(),
        'users_week': User.objects.filter(date_joined__gte=week).count(),
        'phones': User.objects.filter(phone_verified_at__isnull=False).count(),
        'can': moderation.is_moderator(user),
    }
