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
from django.utils.translation import gettext_lazy as _lazy

from .models import Board, BoardMember, Habit, HabitLog

MAX_HABITS = 80            # своих привычек и дел
MAX_BOARDS = 20            # общих трекеров на человека
MAX_MEMBERS = 50
HISTORY = 400              # на столько дней назад считаем серии
MAX_REMINDERS = 6          # таблетки 3–4 раза в день — хватает с запасом
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
        out['emoji'] = str(data['emoji']).strip()[:16] or 'h-check'
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
    if 'part' in data:
        out['part'] = data['part'] if data['part'] in dict(Habit.PARTS) else ''
    if 'per_week' in data:
        try:
            out['per_week'] = max(0, min(int(data['per_week'] or 0), 6))
        except (TypeError, ValueError):
            out['per_week'] = 0
    if 'note' in data:
        out['note'] = str(data['note'] or '').strip()[:200]
    if 'reminders' in data:
        raw = data['reminders']
        items = raw if isinstance(raw, (list, tuple)) else str(raw or '').replace(' ', '').split(',')
        times = []
        for x in items:
            x = str(x).strip()[:5]
            if not x:
                continue
            try:
                hh, mm = x.split(':')
                if not (0 <= int(hh) < 24 and 0 <= int(mm) < 60):
                    raise ValueError
            except ValueError as exc:
                raise TrackerError(_('Время напоминания — в виде 08:30.')) from exc
            norm = f'{int(hh):02d}:{int(mm):02d}'
            if norm not in times:
                times.append(norm)
        if len(times) > MAX_REMINDERS:
            raise TrackerError(_('Не больше {v1} напоминаний в день.').format(v1=MAX_REMINDERS))
        from datetime import time
        out['remind_at'] = time(*map(int, times[0].split(':'))) if times else None
        out['reminders'] = ','.join(times[1:])
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

def set_value(user, habit, day: date, value=None, skip=None, note=None) -> int:
    """Отметить. value не задан — переключить «сделал / не сделал» (у счётчика — +1 до цели, затем сброс).
    skip=True — пропуск по уважительной причине (болезнь, дорога): день не считается и серию не рвёт.
    note — заметка к дню («принял после еды»)."""
    _check_mark_day(day)
    if not habit.due_on(day):
        raise TrackerError(_('В этот день эта привычка не запланирована.'))
    log = HabitLog.objects.filter(habit=habit, user=user, day=day).first()
    current = log.value if log else 0
    if skip is not None:
        log = log or HabitLog(habit=habit, user=user, day=day)
        log.skipped, log.value = bool(skip), 0 if skip else log.value
        if note is not None:
            log.note = str(note).strip()[:200]
        if not log.skipped and not log.value and not log.note:
            if log.pk:
                log.delete()
            return 0
        log.save()
        return log.value
    if value is None:
        new = 0 if current >= habit.target else (habit.target if habit.kind == Habit.CHECK else current + 1)
    else:
        try:
            new = max(0, min(int(value), 1000000))
        except (TypeError, ValueError) as exc:
            raise TrackerError(_('Нужно число.')) from exc
    text = log.note if log and note is None else str(note or '').strip()[:200]
    if new == 0 and not text:
        if log:
            log.delete()
    elif log:
        log.value, log.skipped, log.note = new, False, text
        log.save(update_fields=['value', 'skipped', 'note', 'updated_at'])
    else:
        HabitLog.objects.create(habit=habit, user=user, day=day, value=new, note=text)
    return new


SKIP = -1        # в словаре отметок: пропуск по уважительной причине


def _logs(user, habits, since: date, until: date) -> dict:
    """{(habit_id, day): value} одним запросом; пропуск — SKIP."""
    rows = HabitLog.objects.filter(user=user, habit__in=habits, day__gte=since, day__lte=until).values_list(
        'habit_id', 'day', 'value', 'skipped')
    return {(h, d): (SKIP if sk else v) for h, d, v, sk in rows}


def _done(habit, logs, day) -> bool:
    return logs.get((habit.pk, day), 0) >= habit.target


def _week_done(habit, logs, day) -> int:
    """Сколько раз выполнено на неделе этого дня (для «N раз в неделю»)."""
    monday = day - timedelta(days=day.isoweekday() - 1)
    return sum(1 for i in range(7) if _done(habit, logs, monday + timedelta(days=i)))


def _streaks(habit, logs: dict, today: date) -> tuple:
    """(текущая серия, лучшая серия) в запланированных днях подряд. Сегодня ещё не сделано — серия не рвётся.
    Пропуск по уважительной причине — день не считается вовсе. «N раз в неделю» — серия в неделях."""
    first = max(habit.start_on or habit.created_at.date(), today - timedelta(days=HISTORY))
    if habit.per_week:
        best = run = 0
        current = None
        monday = today - timedelta(days=today.isoweekday() - 1)
        while monday + timedelta(days=6) >= first:
            ok = _week_done(habit, logs, monday) >= habit.per_week
            if ok:
                run += 1
                best = max(best, run)
            else:
                if current is None and monday + timedelta(days=6) < today:
                    current = run
                if monday + timedelta(days=6) < today:
                    run = 0
            monday -= timedelta(days=7)
        return (run if current is None else current), best
    best = run = 0
    current = None
    day = today
    while day >= first:
        if habit.due_on(day) and logs.get((habit.pk, day), 0) != SKIP:
            if _done(habit, logs, day):
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
    raw = logs.get((habit.pk, day), 0)
    value = 0 if raw == SKIP else raw
    streak, best = (0, 0) if habit.once_on else _streaks(habit, logs, today)
    return {
        'part': habit.part, 'per_week': habit.per_week, 'week_done': _week_done(habit, logs, day) if habit.per_week else 0,
        'skipped': raw == SKIP, 'note': habit.note, 'reminders': habit.times(),
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
    # «N раз в неделю» показываем, пока недельная цель не выполнена (или если сделано именно сегодня)
    items = [card(h, logs, day, today, user) for h in habits if h.due_on(day)
             and (not h.per_week or _week_done(h, logs, day) < h.per_week or _done(h, logs, day))]
    notes = dict(HabitLog.objects.filter(user=user, day=day, habit__in=habits).exclude(note='').values_list('habit_id', 'note'))
    for x in items:
        x['log_note'] = notes.get(x['id'], '')
    order = {p: i for i, (p, _n) in enumerate(Habit.PARTS[1:])}
    items.sort(key=lambda x: (x['done'] or x['skipped'], order.get(x['part'], 3), bool(x['board']), x['id']))
    monday = day - timedelta(days=day.isoweekday() - 1)
    week = []
    for i in range(7):
        d = monday + timedelta(days=i)
        due = [h for h in habits if h.due_on(d) and logs.get((h.pk, d), 0) != SKIP
               and (not h.per_week or _done(h, logs, d))]
        done = sum(1 for h in due if _done(h, logs, d))
        week.append({'day': d.isoformat(), 'n': d.day, 'done': done, 'total': len(due), 'today': d == today,
                     'future': d > today})
    done = sum(1 for x in items if x['done'])
    return {'day': day.isoformat(), 'today': today.isoformat(), 'items': items, 'done': done, 'total': len(items),
            'week': week, 'habits_total': len(habits), 'parts': [{'key': k, 'name': str(n)} for k, n in Habit.PARTS],
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
        due = [h for h in habits if h.due_on(d) and (h.start_on or h.created_at.date()) <= d
               and logs.get((h.pk, d), 0) != SKIP and (not h.per_week or _done(h, logs, d))]
        done = sum(1 for h in due if _done(h, logs, d))
        by_day.append({'day': d.isoformat(), 'done': done, 'total': len(due)})
    rows = []
    for h in habits:
        due = [since + timedelta(days=i) for i in range(days)
               if h.due_on(since + timedelta(days=i)) and (h.start_on or h.created_at.date()) <= since + timedelta(days=i)
               and logs.get((h.pk, since + timedelta(days=i)), 0) != SKIP]
        done = sum(1 for d in due if _done(h, logs, d))
        streak, best = _streaks(h, logs, today)
        if h.per_week:                               # процент — по неделям, когда цель выполнена
            weeks = max(1, days // 7)
            met = sum(1 for w in range(weeks) if _week_done(h, logs, today - timedelta(days=7 * w)) >= h.per_week)
            rate = round(100 * met / weeks)
        else:
            rate = round(100 * done / len(due)) if due else 0
        rows.append({'id': h.pk, 'title': h.title, 'emoji': h.emoji, 'color': h.color, 'done': done, 'total': len(due),
                     'rate': rate, 'streak': streak, 'best': best, 'per_week': h.per_week,
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


def create_board(user, title, emoji='h-together', compete=False) -> Board:
    title = (title or '').strip()[:80]
    if len(title) < 2:
        raise TrackerError(_('Дайте название — хотя бы два знака.'))
    if BoardMember.objects.filter(user=user).count() >= MAX_BOARDS:
        raise TrackerError(_('Слишком много общих трекеров.'))
    board = Board.objects.create(owner=user, title=title, emoji=(emoji or 'h-together')[:16], compete=bool(compete),
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
    if board.thread_id:                              # у трекера уже есть общий чат — новичок сразу в нём
        from apps.chat.models import Member
        board.thread.participants.add(user)
        Member.objects.get_or_create(thread_id=board.thread_id, user=user)
    return board


def leave(user, board) -> None:
    if board.owner_id == user.pk:
        raise TrackerError(_('Владелец не может выйти — можно удалить трекер.'))
    BoardMember.objects.filter(board=board, user=user).delete()
    HabitLog.objects.filter(habit__board=board, user=user).delete()
    _drop_from_chat(board, user)


def _drop_from_chat(board, user) -> None:
    if board.thread_id:
        from apps.chat.models import Member
        board.thread.participants.remove(user)
        Member.objects.filter(thread_id=board.thread_id, user=user).delete()


def update_board(user, board, data) -> Board:
    if board.owner_id != user.pk:
        raise TrackerError(_('Менять может только владелец.'), 403)
    if 'title' in data:
        title = str(data['title']).strip()[:80]
        if len(title) < 2:
            raise TrackerError(_('Дайте название — хотя бы два знака.'))
        board.title = title
    if 'emoji' in data:
        board.emoji = str(data['emoji']).strip()[:16] or 'h-together'
    if 'compete' in data:
        board.compete = str(data['compete']).lower() in ('1', 'true', 'on')
    if 'ends_on' in data:
        raw = str(data['ends_on'] or '').strip()
        try:
            board.ends_on = date.fromisoformat(raw[:10]) if raw else None
        except ValueError as exc:
            raise TrackerError(_('Дата указана неверно.')) from exc
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
    _drop_from_chat(board, member)


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
            'people': table, 'period': days, 'invite_code': board.invite_code, **board_extra(user, board, today)}


# ---------- напоминания ----------

def due_reminders(now=None) -> list:
    """Кому напомнить в эту минуту: [(пользователь, привычка)]. Время — местное для автора привычки."""
    now = now or timezone.now()
    out = []
    for h in Habit.objects.filter(archived=False, remind_at__isnull=False).select_related('owner', 'board'):
        local = now.astimezone(dt_timezone.utc) + timedelta(minutes=h.tz_offset)
        if f'{local.hour:02d}:{local.minute:02d}' not in h.times() or not h.due_on(local.date()):
            continue
        users = [m.user for m in h.board.memberships.select_related('user')] if h.board_id else [h.owner]
        done = set(HabitLog.objects.filter(habit=h, day=local.date(), value__gte=h.target).values_list('user_id', flat=True))
        out.extend((u, h) for u in users if u.pk not in done)
    return out


# ---------- готовые привычки (шаблоны) ----------


TEMPLATES = [
    # (ключ, группа, название, значок, цвет, вид, цель, единица, время дня, раз в неделю, дни, напоминания, заметка)
    ('fajr', 'faith', _lazy('Фаджр вовремя'), 'h-sunrise', '#6d5efc', 'check', 1, '', 'morning', 0, '1234567', '', ''),
    ('salah5', 'faith', _lazy('Пять намазов'), 'h-mosque', '#6d5efc', 'count', 5, _lazy('намазов'), '', 0, '1234567', '', ''),
    ('azkar_m', 'faith', _lazy('Утренние азкары'), 'h-sun', '#f59e0b', 'check', 1, '', 'morning', 0, '1234567', '07:00', ''),
    ('azkar_e', 'faith', _lazy('Вечерние азкары'), 'h-moon', '#8b5cf6', 'check', 1, '', 'evening', 0, '1234567', '18:30', ''),
    ('quran', 'faith', _lazy('Коран'), 'h-quran', '#10b981', 'count', 5, _lazy('страниц'), '', 0, '1234567', '', ''),
    ('fast', 'faith', _lazy('Пост в понедельник и четверг'), 'h-moon', '#14b8a6', 'check', 1, '', '', 0, '14', '', _lazy('Сунна')),
    ('sadaqa', 'faith', _lazy('Садака'), 'h-dua', '#ec4899', 'check', 1, '', '', 1, '1234567', '', _lazy('Хотя бы раз в неделю')),
    ('tahajjud', 'faith', _lazy('Тахаджуд'), 'h-star', '#0ea5e9', 'check', 1, '', 'morning', 2, '1234567', '', ''),
    ('water', 'health', _lazy('Вода'), 'h-water', '#0ea5e9', 'count', 8, _lazy('стаканов'), '', 0, '1234567', '', ''),
    ('pills', 'health', _lazy('Таблетки'), 'h-pill', '#ef4444', 'count', 3, _lazy('раза'), '', 0, '1234567', '08:00,14:00,20:00',
     _lazy('По 1 таблетке после еды')),
    ('walk', 'health', _lazy('Прогулка'), 'h-walk', '#10b981', 'count', 30, _lazy('минут'), '', 0, '1234567', '', ''),
    ('sport', 'health', _lazy('Спорт'), 'h-sport', '#f59e0b', 'check', 1, '', '', 3, '1234567', '', ''),
    ('sleep', 'health', _lazy('Лечь до 23:00'), 'h-sleep', '#64748b', 'check', 1, '', 'evening', 0, '1234567', '22:30', ''),
    ('arabic', 'study', _lazy('Арабский: новые слова'), 'h-lang', '#8b5cf6', 'count', 10, _lazy('слов'), '', 0, '1234567', '', ''),
    ('read', 'study', _lazy('Чтение'), 'h-books', '#14b8a6', 'count', 10, _lazy('страниц'), '', 0, '1234567', '', ''),
    ('nophone', 'study', _lazy('Час без телефона'), 'h-nophone', '#64748b', 'check', 1, '', 'evening', 0, '1234567', '', ''),
]
TEMPLATE_GROUPS = [('faith', _lazy('Вера')), ('health', _lazy('Здоровье')), ('study', _lazy('Учёба и польза'))]


def templates() -> list:
    return [{'key': k, 'group': g, 'title': str(title), 'emoji': em, 'color': col, 'kind': kind, 'target': target,
             'unit': str(unit), 'part': part, 'per_week': pw, 'days': days, 'reminders': rem, 'note': str(note)}
            for k, g, title, em, col, kind, target, unit, part, pw, days, rem, note in TEMPLATES]


def add_template(user, key: str, board=None, tz_offset=None) -> Habit:
    """Добавить готовую привычку одним нажатием (потом её можно поменять как угодно)."""
    tpl = next((x for x in templates() if x['key'] == key), None)
    if tpl is None:
        raise TrackerError(_('Не найдено'), 404)
    data = {k: v for k, v in tpl.items() if k not in ('key', 'group')}
    if tz_offset is not None:
        data['tz_offset'] = tz_offset
    return create_habit(user, data, board)


# ---------- одна привычка: календарь за год, история ----------

def habit_detail(user, habit, days: int = 365) -> dict:
    """Календарь-«теплокарта» (как у GitHub): каждый день — сделано, частично, пропуск или нет; плюс итоги."""
    today = timezone.localdate()
    days = max(28, min(int(days or 365), 400))
    since = today - timedelta(days=days - 1)
    logs = _logs(user, [habit], today - timedelta(days=HISTORY), today)
    notes = dict(HabitLog.objects.filter(user=user, habit=habit, day__gte=since).exclude(note='').values_list('day', 'note'))
    cells = []
    for i in range(days):
        d = since + timedelta(days=i)
        raw = logs.get((habit.pk, d), 0)
        due = habit.due_on(d) and (habit.start_on or habit.created_at.date()) <= d
        cells.append({'day': d.isoformat(), 'due': due, 'value': max(0, raw), 'skipped': raw == SKIP,
                      'level': 0 if raw <= 0 else min(4, 1 + (3 * raw) // max(1, habit.target)),
                      'note': notes.get(d, '')})
    streak, best = _streaks(habit, logs, today)
    done_days = [c for c in cells if c['level'] >= 4 or (habit.kind == Habit.CHECK and c['value'])]
    total = sum(c['value'] for c in cells)
    months = {}
    for c in cells:
        key = c['day'][:7]
        m = months.setdefault(key, {'month': key, 'done': 0, 'due': 0})
        m['due'] += 1 if c['due'] and not c['skipped'] else 0
        m['done'] += 1 if c['value'] >= habit.target else 0
    return {'habit': card(habit, logs, today, today, user), 'cells': cells, 'streak': streak, 'best': best,
            'done_days': len(done_days), 'total': total, 'months': list(months.values())[-12:],
            'notes': [{'day': d.isoformat(), 'note': n} for d, n in sorted(notes.items(), reverse=True)[:30]]}


# ---------- общий трекер: срок соревнования, лента активности, общий чат ----------

def board_extra(user, board, today=None) -> dict:
    """Сколько дней осталось, кто победил (если срок вышел), последние отметки участников."""
    today = today or timezone.localdate()
    out = {'ends_on': board.ends_on.isoformat() if board.ends_on else '', 'days_left': None, 'finished': False,
           'chat': board.thread_id}
    if board.ends_on:
        out['days_left'] = max(0, (board.ends_on - today).days)
        out['finished'] = today > board.ends_on
    rows = (HabitLog.objects.filter(habit__board=board, value__gt=0).select_related('user', 'habit')
            .order_by('-updated_at')[:25])
    out['activity'] = [{'name': r.user.get_display_name(), 'user': r.user_id, 'habit': r.habit.title, 'emoji': r.habit.emoji,
                        'value': r.value, 'unit': r.habit.unit, 'done': r.value >= r.habit.target, 'day': r.day.isoformat(),
                        'at': r.updated_at.isoformat(), 'me': r.user_id == user.pk} for r in rows]
    return out


def board_chat(user, board):
    """Общий чат трекера — обычная закрытая группа мессенджера с участниками трекера (создаётся при первом открытии)."""
    from apps.chat import rooms
    from apps.chat.models import Member, Thread
    if not is_member(board, user):
        raise TrackerError(_('Нет доступа'), 403)
    thread = board.thread
    if thread is None:
        if not rooms.enabled(Thread.GROUP):
            raise TrackerError(_('Группы в чатах сейчас выключены.'), 403)
        import secrets as _s
        thread = Thread.objects.create(kind=Thread.GROUP, title=board.title[:120], owner=board.owner,
                                       invite_code=_s.token_urlsafe(12), about=str(_('Чат общего трекера')))
        for m in board.memberships.select_related('user'):
            thread.participants.add(m.user)
            Member.objects.get_or_create(thread=thread, user=m.user,
                                         defaults={'role': Member.OWNER if m.user_id == board.owner_id else Member.MEMBER})
        thread.members_count = thread.participants.count()
        thread.save(update_fields=['members_count'])
        board.thread = thread
        board.save(update_fields=['thread'])
    elif not thread.participants.filter(pk=user.pk).exists():
        thread.participants.add(user)
        Member.objects.get_or_create(thread=thread, user=user)
    return thread
