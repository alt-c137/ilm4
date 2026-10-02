from django import template

from apps.chat.richtext import to_html

register = template.Library()


@register.filter
def rich(text):
    """{{ m.body|rich }} — оформление сообщения (жирный, курсив, скрытый текст, ссылки)."""
    return to_html(text)
