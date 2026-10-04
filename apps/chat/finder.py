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
    from . import services
    if not services.search_allowed(user):                  # слишком частый поиск — без поиска по текстам (он самый тяжёлый)
        return out
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


# ---------- «недавние» и «частые» — экран поиска до того, как человек начал печатать (как в Telegram) ----------

RECENT_MAX = 15
KINDS = ('u', 't', 's')            # человек, чат (диалог, группа, канал), сообщество


def remember(user, kind: str, pk) -> None:
    """Запомнить, что человек открыл это из поиска. Хранится в его настройках: User.ui['recent'] = [['u', 5], ['t', 12], …]."""
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        return
    if kind not in KINDS:
        return
    ui = dict(user.ui or {})
    rows = [r for r in ui.get('recent', []) if isinstance(r, list) and len(r) == 2 and r != [kind, pk]]
    ui['recent'] = ([[kind, pk]] + rows)[:RECENT_MAX]
    user.ui = ui
    user.save(update_fields=['ui'])


def forget_recent(user) -> None:
    ui = dict(user.ui or {})
    if ui.pop('recent', None) is not None:
        user.ui = ui
        user.save(update_fields=['ui'])


def recent(user) -> list:
    """Недавние из поиска: [('u', человек) | ('t', чат) | ('s', сообщество)] — то, что ещё существует и доступно."""
    from django.contrib.auth import get_user_model

    from apps.accounts.models import UserBlock

    from . import services
    from .models import Space, Thread
    rows = [r for r in (user.ui or {}).get('recent', []) if isinstance(r, list) and len(r) == 2 and r[0] in KINDS]
    blocked = UserBlock.ids_for(user)
    people = {u.pk: u for u in get_user_model().objects.filter(pk__in=[r[1] for r in rows if r[0] == 'u'], is_active=True).exclude(pk__in=blocked)}
    threads = {t.pk: t for t in Thread.objects.filter(pk__in=[r[1] for r in rows if r[0] == 't'], closed=False)}
    spaces_ = {s.pk: s for s in Space.objects.filter(pk__in=[r[1] for r in rows if r[0] == 's'], closed=False)}
    out = []
    for kind, pk in rows:
        obj = people.get(pk) if kind == 'u' else threads.get(pk) if kind == 't' else spaces_.get(pk)
        if obj is None or (kind == 't' and not services.can_read(obj, user)):
            continue
        out.append((kind, obj))
    return out


def top_people(user, limit: int = 8) -> list:
    """Кому человек пишет чаще всего (личные диалоги, последние 60 дней) — ряд аватаров над «Недавними»."""
    from datetime import timedelta

    from django.db.models import Count

    from apps.accounts.models import UserBlock

    from .models import Message, Thread
    since = timezone.now() - timedelta(days=60)
    rows = (Message.objects.filter(sender=user, thread__kind=Thread.DIRECT, thread__context_type='', created_at__gte=since)
            .values('thread').annotate(n=Count('id')).order_by('-n')[:limit * 2])
    blocked = UserBlock.ids_for(user)
    out = []
    for t in Thread.objects.filter(pk__in=[r['thread'] for r in rows]).prefetch_related('participants'):
        other = next((p for p in t.participants.all() if p.pk != user.pk), None)
        if other is not None and other.is_active and other.pk not in blocked:
            out.append((next(r['n'] for r in rows if r['thread'] == t.pk), t, other))
    out.sort(key=lambda x: -x[0])
    return [(t, other) for _n, t, other in out[:limit]]

