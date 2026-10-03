"""Что помощник умеет делать за человека. Каждое действие — от имени этого человека и с его правами:
помощник видит только то, что видит он сам, и меняет только его собственные данные (трекер).

Тексты сообщений помощнику не передаются — только названия чатов и число непрочитанных. Исключение — человек сам
включил «помощник может читать мои новые сообщения» (действие recent_messages); чаты никяха не передаются никогда.
Новое умение = описание в TOOLS (или OPT_IN) + функция с тем же именем ниже.
"""
from datetime import date, timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

TOOLS = [
    {'name': 'prayer_times', 'description': 'Время намазов на день для города. Город — по-русски или латиницей (Ташкент, Москва, Стамбул…).',
     'input_schema': {'type': 'object', 'properties': {
         'city': {'type': 'string', 'description': 'Город. Пусто — город человека из профиля или Ташкент.'},
         'date': {'type': 'string', 'description': 'ГГГГ-ММ-ДД; пусто — сегодня.'}}, 'additionalProperties': False}},
    {'name': 'find_places', 'description': 'Найти халяль-места на карте ilm4: мечети, кафе, магазины, мясные лавки, отели.',
     'input_schema': {'type': 'object', 'properties': {
         'query': {'type': 'string', 'description': 'Название или адрес; можно пусто.'},
         'category': {'type': 'string', 'enum': ['', 'mosque', 'cafe', 'shop', 'butcher', 'hotel', 'other']},
         'city': {'type': 'string'}}, 'additionalProperties': False}},
    {'name': 'search_listings', 'description': 'Поиск публикаций ilm4: объявления (buy), вакансии (jobs), услуги (services), попутчики (trips).',
     'input_schema': {'type': 'object', 'properties': {
         'section': {'type': 'string', 'enum': ['buy', 'jobs', 'services', 'trips']},
         'query': {'type': 'string'}, 'city': {'type': 'string'}},
         'required': ['section'], 'additionalProperties': False}},
    {'name': 'tracker_today', 'description': 'Привычки и дела человека на день из его трекера: что сделано, что нет, серии.',
     'input_schema': {'type': 'object', 'properties': {'date': {'type': 'string'}}, 'additionalProperties': False}},
    {'name': 'add_habit', 'description': 'Добавить привычку в трекер человека (повторяется по дням или N раз в неделю).',
     'input_schema': {'type': 'object', 'properties': {
         'title': {'type': 'string'},
         'icon': {'type': 'string', 'enum': ['h-check', 'h-pill', 'h-water', 'h-quran', 'h-mosque', 'h-dua', 'h-run', 'h-walk', 'h-sport', 'h-sleep',
                                             'h-books', 'h-study', 'h-lang', 'h-work', 'h-money', 'h-food', 'h-moon', 'h-sun', 'h-target'],
                  'description': 'Значок привычки (по смыслу).'},
         'target': {'type': 'integer', 'description': 'Сколько в день (стаканов, страниц). 1 — просто «сделал».'},
         'unit': {'type': 'string'}, 'days': {'type': 'string', 'description': 'Дни недели цифрами 1-7, например 135. Пусто — каждый день.'},
         'per_week': {'type': 'integer', 'description': '0 — по дням; 1-6 — столько раз в неделю.'},
         'part': {'type': 'string', 'enum': ['', 'morning', 'day', 'evening']},
         'reminders': {'type': 'string', 'description': 'Время напоминаний через запятую: 08:00,20:00'},
         'note': {'type': 'string'}}, 'required': ['title'], 'additionalProperties': False}},
    {'name': 'mark_habit', 'description': 'Отметить привычку выполненной сегодня (или указать количество).',
     'input_schema': {'type': 'object', 'properties': {'habit_id': {'type': 'integer'}, 'value': {'type': 'integer'}},
                      'required': ['habit_id'], 'additionalProperties': False}},
    {'name': 'schedule_meeting', 'description': 'Поставить встречу или дело на конкретный день с напоминанием (появится в трекере).',
     'input_schema': {'type': 'object', 'properties': {
         'title': {'type': 'string'}, 'date': {'type': 'string', 'description': 'ГГГГ-ММ-ДД'},
         'time': {'type': 'string', 'description': 'ЧЧ:ММ — когда напомнить'}, 'note': {'type': 'string'}},
         'required': ['title', 'date'], 'additionalProperties': False}},
    {'name': 'unread_chats', 'description': 'Сколько непрочитанных в чатах человека (только названия чатов и числа, без текстов).',
     'input_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False}},
    {'name': 'latest_news', 'description': 'Последние новости ilm4.',
     'input_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False}},
]


class ToolError(Exception):
    pass


def _day(value) -> date:
    if not value:
        return timezone.localdate()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ToolError('Дата — в виде ГГГГ-ММ-ДД') from exc


def prayer_times(user, city: str = '', date: str = '') -> dict:
    from apps.prayer.cities import CITIES, DEFAULT_CITY
    from apps.prayer.services import compute_for_city
    want = (city or getattr(user, 'city', '') or '').strip().lower()
    key = DEFAULT_CITY
    if want:
        for k, row in CITIES.items():
            if want in (k.lower(), str(row[0]).lower()) or str(row[0]).lower().startswith(want) or k.startswith(want):
                key = k
                break
        else:
            return {'error': f'Город «{city}» не найден в справочнике ilm4.', 'known': [str(r[0]) for r in CITIES.values()][:40]}
    return {'city': str(CITIES[key][0]), 'date': _day(date).isoformat(), 'times': compute_for_city(key, _day(date))}


def find_places(user, query: str = '', category: str = '', city: str = '') -> dict:
    from apps.core.models import Moderation
    from apps.maps.models import HalalPlace
    qs = HalalPlace.objects.filter(status=Moderation.APPROVED)
    if category:
        qs = qs.filter(category=category)
    if city:
        qs = qs.filter(city__icontains=city)
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(address__icontains=query) | Q(description__icontains=query))
    return {'items': [{'name': p.name, 'category': str(p.get_category_display()), 'city': p.city, 'address': p.address,
                       'phone': p.phone, 'checked': str(p.verification()['label']), 'link': reverse('maps:detail', args=[p.pk])}
                      for p in qs.prefetch_related('confirmations')[:8]]}


def search_listings(user, section: str, query: str = '', city: str = '') -> dict:
    from apps.core.models import Moderation
    from apps.core.publications import BY_KEY
    pub = BY_KEY.get(section)
    if pub is None:
        raise ToolError('Неизвестный раздел')
    model = pub.get_model()
    qs = model.objects.filter(status=Moderation.APPROVED)
    if pub.active:
        qs = qs.filter(**{pub.active: True})
    if query:
        field = 'name' if pub.title == 'name' else 'from_city' if pub.title == 'route' else 'title'
        qs = qs.filter(**{f'{field}__icontains': query}) if section != 'trips' else qs.filter(Q(from_city__icontains=query) | Q(to_city__icontains=query))
    if city and hasattr(model, 'city'):
        qs = qs.filter(city__icontains=city)
    return {'items': [{'title': pub.title_of(o), 'price': str(getattr(o, 'price', '') or getattr(o, 'salary', '') or ''),
                       'city': getattr(o, 'city', '') or '', 'link': pub.url_of(o)} for o in qs.order_by('-pk')[:8]]}


def tracker_today(user, date: str = '') -> dict:
    from apps.tracker import services as tr
    data = tr.day_view(user, _day(date))
    return {'date': data['day'], 'done': data['done'], 'total': data['total'],
            'items': [{'habit_id': x['id'], 'title': x['title'], 'done': x['done'], 'value': x['value'], 'target': x['target'],
                       'unit': x['unit'], 'streak': x['streak']} for x in data['items']]}


def add_habit(user, title: str, icon: str = 'h-check', target: int = 1, unit: str = '', days: str = '', per_week: int = 0,
              part: str = '', reminders: str = '', note: str = '') -> dict:
    from apps.tracker import services as tr
    try:
        h = tr.create_habit(user, {'title': title, 'emoji': icon or 'h-check', 'kind': 'count' if (target or 1) > 1 else 'check',
                                   'target': target or 1, 'unit': unit, 'days': days or '1234567', 'per_week': per_week or 0,
                                   'part': part, 'reminders': reminders, 'note': note})
    except tr.TrackerError as exc:
        raise ToolError(exc.message) from exc
    return {'ok': True, 'habit_id': h.pk, 'link': '/tracker/'}


def mark_habit(user, habit_id: int, value=None) -> dict:
    from apps.tracker import services as tr
    try:
        h = tr.get_habit(user, habit_id)
        v = tr.set_value(user, h, timezone.localdate(), value)
    except tr.TrackerError as exc:
        raise ToolError(exc.message) from exc
    return {'ok': True, 'value': v, 'done': v >= h.target}


def schedule_meeting(user, title: str, date: str, time: str = '', note: str = '') -> dict:
    from apps.tracker import services as tr
    day = _day(date)
    if day < timezone.localdate() - timedelta(days=1):
        raise ToolError('Эта дата уже прошла.')
    try:
        h = tr.create_habit(user, {'title': title[:80], 'emoji': 'h-meet', 'once_on': day.isoformat(), 'reminders': time or '',
                                   'note': note, 'day': day.isoformat()})
    except tr.TrackerError as exc:
        raise ToolError(exc.message) from exc
    return {'ok': True, 'habit_id': h.pk, 'date': day.isoformat(), 'reminder': time or 'без напоминания', 'link': f'/tracker/?day={day}'}


def unread_chats(user) -> dict:
    from apps.chat import services as chat
    rows = [(t, o) for t, o, _m in chat.inbox(user) if t.unread]
    out = []
    for t, o in rows[:15]:
        name = t.title if t.is_room else (o.get_display_name() if o else 'чат')
        out.append({'chat': name, 'unread': t.unread, 'link': f'/chat/{t.pk}/'})
    return {'items': out}


def latest_news(user) -> dict:
    from apps.news.models import NewsPost
    return {'items': [{'title': n.title, 'summary': n.summary, 'link': f'/news/{n.slug}/'} for n in NewsPost.objects.all()[:6]]}


def my_plans(user, days: int = 7) -> dict:
    """Встречи и разовые дела на ближайшие дни (из трекера)."""
    from apps.tracker.models import Habit
    today = timezone.localdate()
    rows = (Habit.objects.filter(owner=user, archived=False, once_on__gte=today, once_on__lte=today + timedelta(days=max(1, min(int(days or 7), 31))))
            .order_by('once_on', 'remind_at')[:20])
    return {'items': [{'habit_id': h.pk, 'title': h.title, 'date': h.once_on.isoformat(), 'reminders': h.times(), 'note': h.note} for h in rows]}


def my_notifications(user) -> dict:
    from apps.core.models import Notification
    rows = Notification.objects.filter(user=user, read=False).order_by('-pk')[:12]
    return {'unread': Notification.objects.filter(user=user, read=False).count(),
            'items': [{'text': n.text[:160], 'link': n.url, 'at': timezone.localtime(n.created_at).strftime('%d.%m %H:%M')} for n in rows]}


def recent_messages(user, limit: int = 15) -> dict:
    """Новые (непрочитанные) сообщения человеку — только если он сам это разрешил. Чаты никяха не передаём."""
    from apps.chat import persona
    from apps.chat import services as chat
    from apps.chat.models import Message
    out = []
    for t, o, _m in chat.inbox(user):
        if not t.unread or t.context_type == persona.NIKAH:
            continue
        name = t.title if t.is_room else (o.get_display_name() if o else 'чат')
        msgs = (Message.objects.visible_to(user).filter(thread=t).exclude(sender=user).select_related('sender').order_by('-pk')[:min(t.unread, 5)])
        for m in reversed(list(msgs)):
            text = m.body[:300] if m.kind == Message.TEXT else f'[{m.get_kind_display()}]'
            out.append({'chat': name, 'from': m.sender.get_display_name(), 'text': text,
                        'at': timezone.localtime(m.created_at).strftime('%d.%m %H:%M'), 'link': f'/chat/{t.pk}/'})
        if len(out) >= max(1, min(int(limit or 15), 40)):
            break
    return {'items': out[:40], 'note': 'Чаты никяха не показываются помощнику.'}


EXTRA = [
    {'name': 'my_plans', 'description': 'Встречи и разовые дела человека на ближайшие дни (из его трекера).',
     'input_schema': {'type': 'object', 'properties': {'days': {'type': 'integer', 'description': 'На сколько дней вперёд, по умолчанию 7.'}},
                      'additionalProperties': False}},
    {'name': 'my_notifications', 'description': 'Непрочитанные уведомления человека на ilm4 (одобрили публикацию, ответили, заявка на место…).',
     'input_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False}},
]
OPT_IN = {
    'recent_messages': {'name': 'recent_messages', 'description': 'Новые непрочитанные сообщения человеку: от кого, в каком чате, текст. '
                        'Используй для отчёта «кто мне написал и о чём».',
                        'input_schema': {'type': 'object', 'properties': {'limit': {'type': 'integer'}}, 'additionalProperties': False}},
}
TOOLS = TOOLS + EXTRA

RUN = {f.__name__: f for f in (prayer_times, find_places, search_listings, tracker_today, add_habit, mark_habit,
                                schedule_meeting, unread_chats, latest_news, my_plans, my_notifications, recent_messages)}

# что показать человеку в переписке, когда помощник что-то сделал
LABELS = {'add_habit': 'Добавил привычку в трекер', 'mark_habit': 'Отметил в трекере',
          'schedule_meeting': 'Поставил в трекер', 'find_places': 'Искал на карте', 'search_listings': 'Искал публикации',
          'prayer_times': 'Посмотрел время намаза', 'tracker_today': 'Посмотрел трекер', 'unread_chats': 'Посмотрел чаты',
          'latest_news': 'Посмотрел новости', 'my_plans': 'Посмотрел планы', 'my_notifications': 'Посмотрел уведомления',
          'recent_messages': 'Прочитал новые сообщения'}


def for_user(read_chats: bool = False) -> list:
    """Набор действий для разговора: чтение сообщений — только с разрешения человека."""
    return TOOLS + ([OPT_IN['recent_messages']] if read_chats else [])


def as_openai(defs: list) -> list:
    """Те же действия в виде, который понимают OpenAI-совместимые сервисы."""
    return [{'type': 'function', 'function': {'name': d['name'], 'description': d['description'], 'parameters': d['input_schema']}} for d in defs]


def run(user, name: str, data: dict, read_chats: bool = False) -> tuple[dict, bool]:
    """Выполнить действие. Возвращает (результат, ошибка ли это)."""
    fn = RUN.get(name)
    if fn is None or (name in OPT_IN and not read_chats):
        return {'error': 'нет такого действия'}, True
    try:
        return fn(user, **(data or {})), False
    except ToolError as exc:
        return {'error': str(exc)}, True
    except (TypeError, ValueError):
        return {'error': 'неверные параметры'}, True


__all__ = ['LABELS', 'TOOLS', 'as_openai', 'for_user', 'run']
