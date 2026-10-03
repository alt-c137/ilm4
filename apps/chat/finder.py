"""Единый поиск в чатах — как в Telegram: одна строка ищет сразу везде.

Свои чаты фильтруются на экране (по названию), а сервер добавляет то, чего на экране нет:
* «Глобальный поиск» — люди по @имени или номеру, публичные каналы и группы, сообщества;
* «Сообщения» — текст во всех моих чатах (тексты в базе зашифрованы, поэтому просматриваем последние SCAN сообщений).
"""
from django.utils import timezone

SCAN = 1500
MIN = 2


def find(user, q: str) -> dict:
    from apps.accounts import people

    from . import persona, rooms, spaces
    from .models import ChatState, Message, Thread
    q = (q or '').strip()[:60]
    out = {'people': [], 'rooms': [], 'spaces': [], 'messages': []}
    if len(q) < MIN:
        return out
    try:
        out['people'] = people.search(user, q, limit=8)
    except people.PeopleError:
        pass                                               # слишком частый поиск по номеру — просто без людей
    name = q.lstrip('@')
    out['rooms'] = list(rooms.catalog(name)[:8])
    if spaces.enabled():
        out['spaces'] = list(spaces.catalog(name)[:6])
    needle = q.casefold()
    cleared = dict(ChatState.objects.filter(user=user, cleared_at__isnull=False).values_list('thread_id', 'cleared_at'))
    hidden = set(ChatState.objects.filter(user=user, hidden=True).values_list('thread_id', flat=True))
    qs = (Message.objects.visible_to(user).filter(thread__participants=user, scheduled_at__isnull=True).exclude(body_enc='')
          .exclude(kind=Message.SYSTEM).select_related('sender', 'thread').order_by('-pk')[:SCAN])
    for m in qs.iterator(chunk_size=300):
        t = m.thread
        if t.pk in hidden or (t.pk in cleared and m.created_at <= cleared[t.pk]):
            continue
        body = m.body
        at = body.casefold().find(needle)
        if at < 0:
            continue
        if t.is_room:
            title = t.title
        elif t.context_type == 'saved':
            title = None
        else:
            title = persona.name_in(t, t.other_participant(user))
        start = max(0, at - 30)
        local = timezone.localtime(m.created_at)
        out['messages'].append({'id': m.pk, 'thread': t.pk, 'title': title, 'saved': t.context_type == 'saved',
                                'room': t.kind if t.kind != Thread.DIRECT else '',
                                'who': '' if not t.is_room else persona.name_in(t, m.sender),
                                'text': ('…' if start else '') + body[start:start + 110], 'time': local.strftime('%d.%m'), 'iso': m.created_at.isoformat()})
        if len(out['messages']) >= 20:
            break
    return out
