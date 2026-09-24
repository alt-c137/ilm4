"""{{ value|tr }} — перевести текст из базы (название раздела, категории, города), если перевод есть.
Нет перевода — выводится как есть. Подключён как builtin (settings.TEMPLATES), {% load %} не нужен."""
from django import template
from django.utils.translation import gettext

register = template.Library()


@register.filter
def tr(value):
    return gettext(str(value)) if value else value
