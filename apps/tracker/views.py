"""Страницы трекера привычек на сайте. Вся логика — в services.py (общая с приложением)."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.decorators import module_required

from . import services as tr
from .models import Habit
from .services import TrackerError

WEEKDAYS = [('1', 'Пн'), ('2', 'Вт'), ('3', 'Ср'), ('4', 'Чт'), ('5', 'Пт'), ('6', 'Сб'), ('7', 'Вс')]
EMOJI = ['✅', '💊', '💧', '📖', '🕌', '🤲', '🏃', '🧘', '🥗', '😴', '📚', '✍️', '🗣', '💼', '🧹', '💰', '📵', '🌙', '☀️', '🎯']


def _get(fn, *args):
    try:
        return fn(*args)
    except TrackerError as exc:
        raise Http404 from exc


@login_required
@module_required('tracker')
def index(request):
    day = tr.parse_day(request.GET.get('day'))
    data = tr.day_view(request.user, day)
    today = timezone.localdate()
    return render(request, 'tracker/index.html', {
        **data, 'day_obj': day, 'is_today': day == today, 'prev': (day - timedelta(days=7)).isoformat(),
        'next': (day + timedelta(days=7)).isoformat(), 'can_mark': today - timedelta(days=7) <= day <= today,
        'percent': round(100 * data['done'] / data['total']) if data['total'] else 0})


@login_required
@module_required('tracker')
@require_POST
def log(request, pk):
    """Отметить привычку (кнопка в списке). Отвечает JSON — страница обновляет строку без перезагрузки."""
    try:
        habit = tr.get_habit(request.user, pk)
        raw = request.POST.get('value')
        value = tr.set_value(request.user, habit, tr.parse_day(request.POST.get('day')), raw if raw not in (None, '') else None)
    except TrackerError as exc:
        return JsonResponse({'error': exc.message}, status=exc.status)
    return JsonResponse({'value': value, 'done': value >= habit.target, 'target': habit.target})


def _form_ctx(request, habit=None, board=None, once=False):
    return {'habit': habit, 'board': board, 'weekdays': WEEKDAYS, 'emoji': EMOJI, 'colors': tr.COLORS,
            'boards': tr.my_boards(request.user), 'once': once, 'today': timezone.localdate().isoformat()}


@login_required
@module_required('tracker')
def habit_new(request):
    board = _get(tr.get_board, request.user, request.GET['board']) if request.GET.get('board') else None
    if request.method == 'POST':
        data = request.POST.dict()
        data['days'] = ''.join(request.POST.getlist('days'))
        if data.get('repeat') != 'once':
            data['once_on'] = ''
        pk = request.POST.get('board')
        try:
            board = tr.get_board(request.user, pk) if pk else None
            tr.create_habit(request.user, data, board)
        except TrackerError as exc:
            messages.error(request, exc.message)
            return render(request, 'tracker/habit_form.html', _form_ctx(request, board=board))
        messages.success(request, _('Добавлено.'))
        return redirect('tracker:board', pk=board.pk) if board else redirect('tracker:index')
    return render(request, 'tracker/habit_form.html', _form_ctx(request, board=board, once=request.GET.get('once') == '1'))


@login_required
@module_required('tracker')
def habit_edit(request, pk):
    habit = _get(tr.get_habit, request.user, pk)
    if not tr.can_edit(habit, request.user):
        raise Http404
    if request.method == 'POST':
        back = redirect('tracker:board', pk=habit.board_id) if habit.board_id else redirect('tracker:index')
        try:
            if request.POST.get('action') == 'delete':
                tr.delete_habit(request.user, habit)
                messages.success(request, _('Удалено.'))
                return back
            data = request.POST.dict()
            data['days'] = ''.join(request.POST.getlist('days'))
            if data.get('repeat') != 'once':
                data['once_on'] = ''
            data['archived'] = '1' if request.POST.get('action') == 'archive' else ''
            tr.update_habit(request.user, habit, data)
        except TrackerError as exc:
            messages.error(request, exc.message)
            return render(request, 'tracker/habit_form.html', _form_ctx(request, habit, habit.board))
        messages.success(request, _('Сохранено.'))
        return back
    return render(request, 'tracker/habit_form.html', _form_ctx(request, habit, habit.board))


@login_required
@module_required('tracker')
def stats(request):
    try:
        days = int(request.GET.get('days', 30))
    except ValueError:
        days = 30
    data = tr.stats(request.user, days)
    top = max([d['total'] for d in data['days']] + [1])
    for d in data['days']:
        d['h'] = round(100 * d['done'] / top)
        d['hh'] = round(100 * d['total'] / top)
        d['label'] = d['day'][8:]
    archived = tr.habits_for(request.user, archived=True)
    return render(request, 'tracker/stats.html', {**data, 'archived': archived, 'periods': (7, 30, 90)})


@login_required
@module_required('tracker')
def board_new(request):
    if request.method == 'POST':
        try:
            board = tr.create_board(request.user, request.POST.get('title', ''), request.POST.get('emoji', '🤝'),
                                    request.POST.get('compete') == 'on')
        except TrackerError as exc:
            messages.error(request, exc.message)
            return render(request, 'tracker/board_form.html', {'emoji': EMOJI})
        return redirect('tracker:board', pk=board.pk)
    return render(request, 'tracker/board_form.html', {'emoji': EMOJI})


@login_required
@module_required('tracker')
def board(request, pk):
    b = _get(tr.get_board, request.user, pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'leave':
                tr.leave(request.user, b)
                return redirect('tracker:index')
            if action == 'delete':
                tr.delete_board(request.user, b)
                return redirect('tracker:index')
            if action == 'compete':
                tr.update_board(request.user, b, {'compete': '' if b.compete else '1'})
            elif action == 'link':
                tr.update_board(request.user, b, {'new_link': '1'})
            elif action == 'remove':
                from django.contrib.auth import get_user_model
                tr.remove_member(request.user, b, get_user_model().objects.get(pk=request.POST.get('user')))
        except (TrackerError, ValueError) as exc:
            messages.error(request, getattr(exc, 'message', str(exc)))
        return redirect('tracker:board', pk=pk)
    try:
        days = int(request.GET.get('days', 7))
    except ValueError:
        days = 7
    day = tr.parse_day(request.GET.get('day'))
    data = tr.board_view(request.user, b, day, days)
    return render(request, 'tracker/board.html', {
        **data, 'board': b, 'invite_link': request.build_absolute_uri(f'/tracker/join/{b.invite_code}/'),
        'can_mark': timezone.localdate() - timedelta(days=7) <= day <= timezone.localdate(), 'periods': (7, 30)})


@login_required
@module_required('tracker')
def join(request, code):
    b = tr.by_code(code)
    if b is None:
        raise Http404
    if request.method == 'POST':
        try:
            tr.join(request.user, code)
        except TrackerError as exc:
            messages.error(request, exc.message)
            return redirect('tracker:index')
        return redirect('tracker:board', pk=b.pk)
    if tr.is_member(b, request.user):
        return redirect('tracker:board', pk=b.pk)
    return render(request, 'tracker/join.html', {'board': b, 'habits': Habit.objects.filter(board=b, archived=False)[:12]})
