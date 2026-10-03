from django import template

from apps.chat.richtext import to_html

register = template.Library()


@register.filter
def rich(text):
    """{{ m.body|rich }} — оформление сообщения (жирный, курсив, скрытый текст, ссылки)."""
    return to_html(text)


@register.filter
def chat_name(message):
    """Имя автора так, как его видят в этом чате (в чате никяха — из анкеты, а не из основного профиля)."""
    from apps.chat import persona
    return persona.name_by_thread_id(message.thread_id, message.sender)
