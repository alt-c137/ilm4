"""API: трекер привычек — день, отметки, статистика для графиков, общие трекеры."""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from apps.tracker import services as tr
from apps.tracker.services import TrackerError

from .base import ApiError, abs_url, api, file_url


def _wrap(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except TrackerError as exc:
        raise ApiError(exc.message, exc.status) from exc


def _board_json(request, data: dict) -> dict:
    data['invite_link'] = abs_url(request, f'/tracker/join/{data.pop("invite_code")}/')
    for p in data['people']:
        p['avatar'] = abs_url(request, p['avatar']) if p['avatar'] else ''
    return data


@api(auth=True, module='tracker')
def day(request):
    """?day=ГГГГ-ММ-ДД — что запланировано и что сделано; неделя; мои общие трекеры."""
    return tr.day_view(request.user, tr.parse_day(request.GET.get('day')))


@api(auth=True, module='tracker')
def stats(request):
    board = _wrap(tr.get_board, request.user, request.GET['board']) if request.GET.get('board') else None
    return tr.stats(request.user, request.GET.get('days') or 30, board)


@api(auth=True, module='tracker')
def habits(request):
    """Все мои привычки (и архив) — для экрана «Управлять»."""
    from django.utils import timezone
    today = timezone.localdate()
    out = []
    for archived in (False, True):
        rows = list(tr.habits_for(request.user, archived=archived))
        logs = tr._logs(request.user, rows, today, today)
        out += [tr.card(h, logs, today, today, request.user) for h in rows]
    return {'items': out, 'colors': tr.COLORS}


@api(methods=('POST',), auth=True, module='tracker')
def habit_create(request):
    d = request.data
    board = _wrap(tr.get_board, request.user, d['board']) if d.get('board') else None
    habit = _wrap(tr.create_habit, request.user, d, board)
    return {'id': habit.pk}


@api(methods=('GET', 'POST', 'DELETE'), auth=True, module='tracker')
def habit(request, pk):
    from django.utils import timezone
    h = _wrap(tr.get_habit, request.user, pk)
    if request.method == 'DELETE':
        _wrap(tr.delete_habit, request.user, h)
        return {'ok': True}
    if request.method == 'POST':
        h = _wrap(tr.update_habit, request.user, h, request.data)
    today = timezone.localdate()
    return tr.card(h, tr._logs(request.user, [h], today - tr.timedelta(days=tr.HISTORY), today), today, today, request.user)


@api(methods=('POST',), auth=True, module='tracker')
def habit_log(request, pk):
    """Отметить: {'day': …, 'value': число} или без value — переключить."""
    h = _wrap(tr.get_habit, request.user, pk)
    d = request.data
    day = tr.parse_day(d.get('day'))
    if 'skip' in d:                                  # пропуск по уважительной причине
        value = _wrap(tr.set_value, request.user, h, day, skip=str(d['skip']).lower() in ('1', 'true'), note=d.get('note'))
    elif 'note' in d and 'value' not in d:           # только заметка к дню
        from apps.tracker.models import HabitLog
        cur = HabitLog.objects.filter(habit=h, user=request.user, day=day).values_list('value', flat=True).first() or 0
        value = _wrap(tr.set_value, request.user, h, day, value=cur, note=d.get('note'))
    else:
        value = _wrap(tr.set_value, request.user, h, day, d.get('value') if 'value' in d else None)
    return {'value': value, 'done': value >= h.target}


@api(auth=True, module='tracker')
def habit_detail(request, pk):
    """Календарь за год, серии, итоги по месяцам, заметки."""
    h = _wrap(tr.get_habit, request.user, pk)
    return tr.habit_detail(request.user, h, request.GET.get('days') or 365)


@api(methods=('GET', 'POST'), auth=True, module='tracker')
def templates(request):
    """Готовые привычки. POST {'key', 'board'?, 'tz_offset'?} — добавить."""
    if request.method == 'POST':
        d = request.data
        board = _wrap(tr.get_board, request.user, d['board']) if d.get('board') else None
        tz = d.get('tz_offset')
        habit = _wrap(tr.add_template, request.user, str(d.get('key', '')), board, int(tz) if str(tz or '').lstrip('-').isdigit() else None)
        return {'id': habit.pk}
    return {'groups': [{'key': k, 'name': str(n)} for k, n in tr.TEMPLATE_GROUPS], 'items': tr.templates()}


@api(methods=('POST',), auth=True, module='tracker')
def board_chat(request, pk):
    b = _wrap(tr.get_board, request.user, pk)
    return {'thread': _wrap(tr.board_chat, request.user, b).pk}


@api(methods=('POST',), auth=True, module='tracker')
def board_create(request):
    d = request.data
    board = _wrap(tr.create_board, request.user, d.get('title', ''), str(d.get('emoji', 'h-together')),
                  str(d.get('compete', '')).lower() in ('1', 'true', 'on'))
    return {'id': board.pk}


@api(methods=('GET', 'POST', 'DELETE'), auth=True, module='tracker')
def board(request, pk):
    b = _wrap(tr.get_board, request.user, pk)
    if request.method == 'DELETE':
        _wrap(tr.delete_board, request.user, b)
        return {'ok': True}
    if request.method == 'POST':
        d = request.data
        if d.get('leave'):
            _wrap(tr.leave, request.user, b)
            return {'ok': True, 'left': True}
        if d.get('remove'):
            _wrap(tr.remove_member, request.user, b, get_object_or_404(get_user_model(), pk=d['remove']))
        else:
            b = _wrap(tr.update_board, request.user, b, d)
    src = request.GET if request.method == 'GET' else request.data
    return _board_json(request, tr.board_view(request.user, b, tr.parse_day(src.get('day')), src.get('days') or 7))


@api(methods=('GET', 'POST'), auth=True, module='tracker')
def board_join(request, code):
    """Ссылка-приглашение: GET — куда зовут, POST — вступить."""
    b = tr.by_code(code)
    if b is None:
        raise ApiError('not found', 404, 'not_found')
    if request.method == 'POST':
        b = _wrap(tr.join, request.user, code)
    return {'id': b.pk, 'title': b.title, 'emoji': b.emoji, 'members': b.memberships.count(),
            'member': tr.is_member(b, request.user), 'owner_name': b.owner.get_display_name(),
            'owner_avatar': file_url(request, b.owner.avatar)}
