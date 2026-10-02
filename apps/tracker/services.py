"""Трекер привычек: что нужно сегодня, отметки, серии дней, статистика для графиков, общие трекеры.

Сайт и приложение работают через эти функции — правила одни. «День» присылает клиент
(у человека может быть другой часовой пояс), но не дальше суток от серверного.
"""
import secrets
from datetime import date, timedelta
from datetime import timezone as dt_timezone

from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Board, BoardMember, Habit, HabitLog

MAX_HABITS = 80            # своих привычек и дел
MAX_BOARDS = 20            # общих трекеров на человека
MAX_MEMBERS = 50
HISTORY = 400              # на столько дней назад считаем серии
COLORS = ['#6d5efc', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#8b5cf6', '#14b8a6', '#64748b']


class TrackerError(Exception):
    def __init__(self, message, status=400):
        super().__init__(str(message))
        self.message, self.status = str(message), status


def parse_day(value) -> date:
    """День от клиента (ГГГГ-ММ-ДД). Пусто или мусор — сегодня по времени сервера."""
    today = timezone.localdate()
    try:
        day = date.fromisoformat(str(value)[:10])
    except ValueError:
        return today
    return day


def _check_mark_day(day: date) -> None:
    """Отмечать можно сегодня и прошлую неделю (забыл отметить вчера), будущее — нет."""
    today = timezone.localdate()
    if day > today + timedelta(days=1) or day < today - timedelta(days=7):
        raise TrackerError(_('Отмечать можно сегодняшний день и прошедшую неделю.'))


# ---------- привычки ----------

def my_boards(user):
    return Board.objects.filter(members=user).order_by('created_at')


def habits_for(user, board=None, archived=False):
    """Привычки человека: личные и из общих трекеров, где он участник."""
    qs = Habit.objects.filter(archived=archived).select_related('board')
    if board is not None:
        return qs.filter(board=board)
    return qs.filter(Q(board__isnull=True, owner=user) | Q(board__members=user)).distinct()


def _clean(data, habit=None) -> dict:
    out = {}
    if 'title' in data or habit is None:
        title = str(data.get('title', '')).strip()[:80]
        if len(title) < 2:
            raise TrackerError(_('Напишите, что нужно делать, — хотя бы два знака.'))
        out['title'] = title
    if 'emoji' in data:
        out['emoji'] = str(data['emoji']).strip()[:8] or '✅'
    if 'color' in data:
        color = str(data['color']).strip()
        out['color'] = color if color in COLORS else COLORS[0]
    if 'kind' in data:
        out['kind'] = Habit.COUNT if data['kind'] == Habit.COUNT else Habit.CHECK
    if 'target' in data:
        try:
            out['target'] = max(1, min(int(data['target'] or 1), 100000))
        except (TypeError, ValueError):
            out['target'] = 1
    if 'unit' in data:
        out['unit'] = str(data['unit']).strip()[:16]
    if 'days' in data:
        days = ''.join(sorted({ch for ch in str(data['days']) if ch in '1234567'}))
        out['days'] = days or '1234567'
    if 'once_on' in data:
        raw = str(data['once_on'] or '').strip()
        try:
            out['once_on'] = date.fromisoformat(raw[:10]) if raw else None
        except ValueError as exc:
            raise TrackerError(_('Дата указана неверно.')) from exc
    if 'remind_at' in data:
        raw = str(data['remind_at'] or '').strip()
        if raw:
            try:
                hh, mm = raw[:5].split(':')
                from datetime import time
                out['remind_at'] = time(int(hh), int(mm))
            except ValueError as exc:
                raise TrackerError(_('Время напоминания — в виде 08:30.')) from exc
        else:
            out['remind_at'] = None
    if 'tz_offset' in data:
        try:
            out['tz_offset'] = max(-720, min(int(data['tz_offset']), 840))
        except (TypeError, ValueError):
            pass
    if out.get('kind', habit.kind if habit else Habit.CHECK) == Habit.CHECK:
        out['target'] = 1
    return out


def create_habit(user, data, board=None) -> Habit:
    if board is not None and not is_member(board, user):
        raise TrackerError(_('Нет доступа'), 403)
    if Habit.objects.filter(owner=user, archived=False).count() >= MAX_HABITS:
        raise TrackerError(_('Слишком много привычек — уберите лишние в архив.'))
    fields = _clean(data)
    fields.setdefault('start_on', parse_day(data.get('day')))
    return Habit.objects.create(owner=user, board=board, order=Habit.objects.filter(owner=user).count(), **fields)


def can_edit(habit, user) -> bool:
    """Личную привычку правит хозяин; общую — тот, кто её добавил, и владелец трекера."""
    return habit.owner_id == user.pk or (habit.board_id is not None and habit.board.owner_id == user.pk)


def get_habit(user, pk) -> Habit:
    habit = Habit.objects.select_related('board').filter(pk=pk).first()
    if habit is None or not (habit.owner_id == user.pk if habit.board_id is None else is_member(habit.board, user)):
        raise TrackerError(_('Не найдено'), 404)
    return habit


def update_habit(user, habit, data) -> Habit:
    if not can_edit(habit, user):
        raise TrackerError(_('Изменить может тот, кто добавил, или владелец трекера.'), 403)
    for k, v in _clean(data, habit).items():
        setattr(habit, k, v)
    if 'archived' in data:
        habit.archived = str(data['archived']).lower() in ('1', 'true', 'on')
    habit.save()
    return habit


def delete_habit(user, habit) -> None:
    if not can_edit(habit, user):
        raise TrackerError(_('Удалить может тот, кто добавил, или владелец трекера.'), 403)
    habit.delete()


# ---------- отметки ----------

def set_value(user, habit, day: date, value=None) -> int:
    """Отметить. value не задан — переключить «сделал / не сделал» (у счётчика — +1 до цели, затем сброс)."""
    _check_mark_day(day)
    if not habit.due_on(day):
        raise TrackerError(_('В этот день эта привычка не запланирована.'))
    log = HabitLog.objects.filter(habit=habit, user=user, day=day).first()
    current = log.value if log else 0
    if value is None:
        new = 0 if current >= habit.target else (habit.target if habit.kind == Habit.CHECK else current + 1)
    else:
        try:
            new = max(0, min(int(value), 1000000))
        except (TypeError, ValueError) as exc:
            raise TrackerError(_('Нужно число.')) from exc
    if new == 0:
        if log:
            log.delete()
    elif log:
        log.value = new
        log.save(update_fields=['value', 'updated_at'])
    else:
        HabitLog.objects.create(habit=habit, user=user, day=day, value=new)
    return new


def _logs(user, habits, since: date, until: date) -> dict:
    """{(habit_id, day): value} одним запросом."""
    rows = HabitLog.objects.filter(user=user, habit__in=habits, day__gte=since, day__lte=until).values_list(
        'habit_id', 'day', 'value')
    return {(h, d): v for h, d, v in rows}


def _streaks(habit, logs: dict, today: date) -> tuple:
    """(текущая серия, лучшая серия) в запланированных днях подряд. Сегодня ещё не сделано — серия не рвётся."""
    best = run = 0
    current = None
    first = max(habit.start_on or habit.created_at.date(), today - timedelta(days=HISTORY))
    day = today
    while day >= first:
        if habit.due_on(day):
            done = logs.get((habit.pk, day), 0) >= habit.target
            if done:
                run += 1
                best = max(best, run)
            else:
                if current is None and day != today:
                    current = run
                if day != today:
                    run = 0
        day -= timedelta(days=1)
    if current is None:
        current = run
    return current, best


def card(habit, logs: dict, day: date, today: date, user) -> dict:
    value = logs.get((habit.pk, day), 0)
    streak, best = (0, 0) if habit.once_on else _streaks(habit, logs, today)
    return {
        'id': habit.pk, 'title': habit.title, 'emoji': habit.emoji, 'color': habit.color, 'kind': habit.kind,
        'target': habit.target, 'unit': habit.unit, 'days': habit.days,
        'once_on': habit.once_on.isoformat() if habit.once_on else '',
        'remind_at': habit.remind_at.strftime('%H:%M') if habit.remind_at else '',
        'board': habit.board_id, 'board_title': habit.board.title if habit.board_id else '',
        'value': value, 'done': value >= habit.target, 'due': habit.due_on(day),
        'streak': streak, 'best': best, 'can_edit': can_edit(habit, user), 'archived': habit.archived,
    }


def day_view(user, day: date) -> dict:
    """Экран «Сегодня»: что запланировано на день, сколько сделано, неделя вокруг него."""
    today = timezone.localdate()
    habits = list(habits_for(user))
    logs = _logs(user, habits, today - timedelta(days=HISTORY), today + timedelta(days=1))
    items = [card(h, logs, day, today, user) for h in habits if h.due_on(day)]
    items.sort(key=lambda x: (x['done'], bool(x['board']), x['id']))
    monday = day - timedelta(days=day.isoweekday() - 1)
    week = []
    for i in range(7):
        d = monday + timedelta(days=i)
        due = [h for h in habits if h.due_on(d)]
        done = sum(1 for h in due if logs.get((h.pk, d), 0) >= h.target)
        week.append({'day': d.isoformat(), 'n': d.day, 'done': done, 'total': len(due), 'today': d == today,
                     'future': d > today})
    done = sum(1 for x in items if x['done'])
    return {'day': day.isoformat(), 'today': today.isoformat(), 'items': items, 'done': done, 'total': len(items),
            'week': week, 'habits_total': len(habits),
            'boards': [board_card(b, user) for b in my_boards(user)]}


def stats(user, days: int = 30, board=None) -> dict:
    """Для графиков: по дням — сколько выполнено из запланированного; по привычкам — процент и серии."""
    days = max(7, min(int(days or 30), 180))
    today = timezone.localdate()
    since = today - timedelta(days=days - 1)
    habits = [h for h in habits_for(user, board) if not h.once_on]
    logs = _logs(user, habits, today - timedelta(days=HISTORY), today)
    by_day = []
    for i in range(days):
        d = since + timedelta(days=i)
        due = [h for h in habits if h.due_on(d) and (h.start_on or h.created_at.date()) <= d]
        done = sum(1 for h in due if logs.get((h.pk, d), 0) >= h.target)
        by_day.append({'day': d.isoformat(), 'done': done, 'total': len(due)})
    rows = []
    for h in habits:
        due = [since + timedelta(days=i) for i in range(days)
               if h.due_on(since + timedelta(days=i)) and (h.start_on or h.created_at.date()) <= since + timedelta(days=i)]
        done = sum(1 for d in due if logs.get((h.pk, d), 0) >= h.target)
        streak, best = _streaks(h, logs, today)
        rows.append({'id': h.pk, 'title': h.title, 'emoji': h.emoji, 'color': h.color, 'done': done, 'total': len(due),
                     'rate': round(100 * done / len(due)) if due else 0, 'streak': streak, 'best': best,
                     'sum': sum(logs.get((h.pk, d), 0) for d in due) if h.kind == Habit.COUNT else 0, 'unit': h.unit,
                     'cells': [1 if logs.get((h.pk, d), 0) >= h.target else 0 for d in due][-35:]})
    total = sum(x['total'] for x in by_day)
    done = sum(x['done'] for x in by_day)
    perfect = sum(1 for x in by_day if x['total'] and x['done'] == x['total'])
    return {'days': by_day, 'habits': rows, 'rate': round(100 * done / total) if total else 0, 'done': done,
            'total': total, 'perfect_days': perfect, 'period': days}


# ---------- общие трекеры ----------

def is_member(board, user) -> bool:
    return BoardMember.objects.filter(board=board, user=user).exists()


def board_card(board, user) -> dict:
    return {'id': board.pk, 'title': board.title, 'emoji': board.emoji, 'compete': board.compete,
            'members': board.memberships.count(), 'owner': board.owner_id == user.pk}


def create_board(user, title, emoji='🤝', compete=False) -> Board:
    title = (title or '').strip()[:80]
    if len(title) < 2:
        raise TrackerError(_('Дайте название — хотя бы два знака.'))
    if BoardMember.objects.filter(user=user).count() >= MAX_BOARDS:
        raise TrackerError(_('Слишком много общих трекеров.'))
    board = Board.objects.create(owner=user, title=title, emoji=(emoji or '🤝')[:8], compete=bool(compete),
                                 invite_code=secrets.token_urlsafe(9))
    BoardMember.objects.create(board=board, user=user)
    return board


def get_board(user, pk) -> Board:
    board = Board.objects.filter(pk=pk).first()
    if board is None or not is_member(board, user):
        raise TrackerError(_('Не найдено'), 404)
    return board


def by_code(code):
    return Board.objects.filter(invite_code=code).first() if code else None


def join(user, code) -> Board:
    board = by_code(code)
    if board is None:
        raise TrackerError(_('Ссылка недействительна.'), 404)
    if is_member(board, user):
        return board
    from apps.accounts.models import UserBlock
    if UserBlock.between(user, board.owner):
        raise TrackerError(_('Нет доступа'), 403)
    if board.memberships.count() >= MAX_MEMBERS:
        raise TrackerError(_('В этом трекере уже максимум участников.'))
    if BoardMember.objects.filter(user=user).count() >= MAX_BOARDS:
        raise TrackerError(_('Слишком много общих трекеров.'))
    BoardMember.objects.create(board=board, user=user)
    return board


def leave(user, board) -> None:
    if board.owner_id == user.pk:
        raise TrackerError(_('Владелец не может выйти — можно удалить трекер.'))
    BoardMember.objects.filter(board=board, user=user).delete()
    HabitLog.objects.filter(habit__board=board, user=user).delete()


def update_board(user, board, data) -> Board:
    if board.owner_id != user.pk:
        raise TrackerError(_('Менять может только владелец.'), 403)
    if 'title' in data:
        title = str(data['title']).strip()[:80]
        if len(title) < 2:
            raise TrackerError(_('Дайте название — хотя бы два знака.'))
        board.title = title
    if 'emoji' in data:
        board.emoji = str(data['emoji']).strip()[:8] or '🤝'
    if 'compete' in data:
        board.compete = str(data['compete']).lower() in ('1', 'true', 'on')
    if data.get('new_link'):
        board.invite_code = secrets.token_urlsafe(9)
    board.save()
    return board


def delete_board(user, board) -> None:
    if board.owner_id != user.pk:
        raise TrackerError(_('Удалить может только владелец.'), 403)
    board.delete()


def remove_member(user, board, member) -> None:
    if board.owner_id != user.pk or member.pk == user.pk:
        raise TrackerError(_('Убирать участников может только владелец.'), 403)
    BoardMember.objects.filter(board=board, user=member).delete()
    HabitLog.objects.filter(habit__board=board, user=member).delete()


def board_view(user, board, day: date, days: int = 7) -> dict:
    """Общий трекер: привычки с отметками каждого за день и таблица за период (если включено соревнование)."""
    today = timezone.localdate()
    days = max(1, min(int(days or 7), 90))
    since = today - timedelta(days=days - 1)
    habits = list(habits_for(user, board))
    people = [m.user for m in board.memberships.select_related('user').order_by('joined_at')]
    rows = HabitLog.objects.filter(habit__in=habits, day__gte=min(since, day), day__lte=max(today, day)).values_list(
        'habit_id', 'user_id', 'day', 'value')
    logs = {(h, u, d): v for h, u, d, v in rows}
    target = {h.pk: h.target for h in habits}

    def done(h, u, d) -> bool:
        return logs.get((h, u, d), 0) >= target[h]

    mine = _logs(user, habits, today - timedelta(days=HISTORY), today + timedelta(days=1))
    items = []
    for h in habits:
        if not h.due_on(day):
            continue
        item = card(h, mine, day, today, user)
        item['who'] = [{'id': p.pk, 'name': p.get_display_name(), 'done': done(h.pk, p.pk, day)} for p in people]
        items.append(item)
    table = []
    for p in people:
        due = points = 0
        for i in range(days):
            d = since + timedelta(days=i)
            for h in habits:
                if h.due_on(d) and not h.once_on and (h.start_on or h.created_at.date()) <= d:
                    due += 1
                    points += 1 if done(h.pk, p.pk, d) else 0
        table.append({'id': p.pk, 'name': p.get_display_name(), 'avatar': p.avatar.url if p.avatar else '',
                      'points': points, 'total': due, 'rate': round(100 * points / due) if due else 0,
                      'me': p.pk == user.pk, 'owner': p.pk == board.owner_id})
    if board.compete:
        table.sort(key=lambda x: (-x['points'], x['name']))
        place = 0
        for i, row in enumerate(table):
            if i == 0 or row['points'] != table[i - 1]['points']:
                place = i + 1
            row['place'] = place
    return {**board_card(board, user), 'day': day.isoformat(), 'today': today.isoformat(), 'items': items,
            'people': table, 'period': days, 'invite_code': board.invite_code}


# ---------- напоминания ----------

def due_reminders(now=None) -> list:
    """Кому напомнить в эту минуту: [(пользователь, привычка)]. Время — местное для автора привычки."""
    now = now or timezone.now()
    out = []
    for h in Habit.objects.filter(archived=False, remind_at__isnull=False).select_related('owner', 'board'):
        local = now.astimezone(dt_timezone.utc) + timedelta(minutes=h.tz_offset)
        if (local.hour, local.minute) != (h.remind_at.hour, h.remind_at.minute) or not h.due_on(local.date()):
            continue
        users = [m.user for m in h.board.memberships.select_related('user')] if h.board_id else [h.owner]
        done = set(HabitLog.objects.filter(habit=h, day=local.date(), value__gte=h.target).values_list('user_id', flat=True))
        out.extend((u, h) for u in users if u.pk not in done)
    return out
