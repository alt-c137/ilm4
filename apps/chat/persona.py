"""«Маски»: в каком виде человек показан собеседнику в чате раздела.

Аккаунт один (один вход, один номер, одна блокировка), но разделы не должны выдавать друг друга:
* чат никяха — собеседник видит имя из анкеты никяха, без аватара, без «в сети» и без перехода в основной профиль
  (там @имя, лента, объявления, номер). Ссылка ведёт в анкету никяха;
* остальные чаты — обычный профиль (приватность — в настройках человека).

Новая маска для раздела = ветка в mask(); экраны берут имя только через name_in() / mask().
"""
from django.urls import reverse
from django.utils.translation import gettext as _

NIKAH = 'nikah'


def mask(thread, person) -> dict | None:
    """Маска человека в этом чате или None, если показываем обычный профиль."""
    if person is None or thread is None or getattr(thread, 'context_type', '') != NIKAH:
        return None
    profile = getattr(person, 'nikah_profile', None)
    name = (profile.name if profile is not None and profile.name else '') or str(_('Анкета никяха'))
    return {'name': name, 'link': reverse('nikah:detail', args=[profile.pk]) if profile is not None else '',
            'profile_id': profile.pk if profile is not None else None}


def name_in(thread, person) -> str:
    """Имя человека так, как его видят в этом чате (подписи сообщений, уведомления, «печатает…»)."""
    if person is None:
        return str(_('Удалённый аккаунт'))
    if getattr(thread, 'space_id', None):                 # канал сообщества — свой ник в этом сообществе
        from . import spaces
        return spaces.nick_of(thread.space_id, person)
    m = mask(thread, person)
    return m['name'] if m else person.get_display_name()


def name_by_thread_id(thread_id, person) -> str:
    """То же, когда под рукой только номер чата (сообщения в списке): тип чата не меняется, поэтому берём его из кеша."""
    from django.core.cache import cache

    from .models import Thread
    if person is None:
        return str(_('Удалённый аккаунт'))
    key = f'chat:ctx:{thread_id}'
    meta = cache.get(key)
    if meta is None:
        row = Thread.objects.filter(pk=thread_id).values_list('context_type', 'space_id').first() or ('', None)
        meta = f'{row[0]}|{row[1] or ""}'
        cache.set(key, meta, 3600)
    ctx, _sep, space_id = meta.partition('|')
    if space_id:
        from . import spaces
        return spaces.nick_of(int(space_id), person)
    if ctx != NIKAH:
        return person.get_display_name()
    profile = getattr(person, 'nikah_profile', None)
    return (profile.name if profile is not None and profile.name else '') or str(_('Анкета никяха'))
