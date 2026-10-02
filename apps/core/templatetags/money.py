"""Цены: {% money listing.price listing.currency %} → «1 200 000 сум ≈ $95» (см. apps/core/money.py)."""
from django import template
from django.utils.html import format_html

from .. import money as m

register = template.Library()


@register.simple_tag(takes_context=True)
def money(context, amount, code, free=''):
    """Цена в валюте автора и рядом «≈» в валюте посетителя."""
    if not amount:
        return free
    extra = m.approx(amount, code, context.get('request'))
    if extra:
        return format_html('{} <span class="approx">{}</span>', m.fmt(amount, code), extra)
    return m.fmt(amount, code)


@register.simple_tag(takes_context=True)
def my_currency(context):
    return m.viewer_currency(context.get('request'))


@register.simple_tag
def currencies():
    return m.choices_json()
