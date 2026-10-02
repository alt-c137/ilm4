"""Трекер привычек: отметки, серии, разовые дела, статистика, общий трекер и соревнование, сайт и API."""
import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.api.models import ApiToken
from apps.core.models import ModuleConfig, Notification
from apps.tracker import services as tr
from apps.tracker.models import Habit, HabitLog

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def pair(db, settings):
    settings.PUSH_DISABLED = True
    ModuleConfig.objects.update_or_create(key='tracker', defaults={'name': 'Трекер', 'status': 'on'})
    return [User.objects.create_user(n, f'{n}@x.com', 'x', first_name=n.title()) for n in ('ali', 'umar', 'zayd')]


def call(client, method, url, user, data=None):
    headers = {'HTTP_AUTHORIZATION': f'Bearer {ApiToken.issue(user, "test")}'}
    if method == 'get':
        return client.get(url, data or {}, **headers)
    if method == 'delete':
        return client.delete(url, **headers)
    return client.post(url, json.dumps(data or {}), content_type='application/json', **headers)


def test_check_and_count_habits_streak(pair):
    ali = pair[0]
    today = timezone.localdate()
    pills = tr.create_habit(ali, {'title': 'Выпить витамины', 'emoji': '💊'})
    water = tr.create_habit(ali, {'title': 'Вода', 'kind': 'count', 'target': 3, 'unit': 'стаканов'})
    Habit.objects.filter(pk__in=[pills.pk, water.pk]).update(start_on=today - timedelta(days=10))
    pills.refresh_from_db()
    water.refresh_from_db()
    # галочка: переключается
    assert tr.set_value(ali, pills, today) == 1
    assert tr.set_value(ali, pills, today) == 0
    # счётчик: +1 до цели, дальше — сброс; можно задать число
    assert [tr.set_value(ali, water, today) for _ in range(4)] == [1, 2, 3, 0]
    assert tr.set_value(ali, water, today, 3) == 3
    # серия: три прошлых дня подряд + сегодня ещё не отмечено — серия не рвётся
    for i in (1, 2, 3):
        HabitLog.objects.create(habit=pills, user=ali, day=today - timedelta(days=i), value=1)
    view = tr.day_view(ali, today)
    item = next(x for x in view['items'] if x['id'] == pills.pk)
    assert item['streak'] == 3 and item['best'] == 3 and not item['done']
    assert view['done'] == 1 and view['total'] == 2
    tr.set_value(ali, pills, today)
    assert next(x for x in tr.day_view(ali, today)['items'] if x['id'] == pills.pk)['streak'] == 4
    # пропуск рвёт серию
    HabitLog.objects.filter(habit=pills, day=today - timedelta(days=1)).delete()
    assert next(x for x in tr.day_view(ali, today)['items'] if x['id'] == pills.pk)['streak'] == 1
    # в будущее и в давнее прошлое отмечать нельзя
    for bad in (today + timedelta(days=3), today - timedelta(days=20)):
        with pytest.raises(tr.TrackerError):
            tr.set_value(ali, pills, bad)


def test_weekdays_and_one_off_task(pair):
    ali = pair[0]
    today = timezone.localdate()
    other = str((today.isoweekday() % 7) + 1)                       # завтрашний день недели
    tr.create_habit(ali, {'title': 'Спортзал', 'days': other})
    task = tr.create_habit(ali, {'title': 'Забрать справку', 'once_on': today.isoformat()})
    titles = [x['title'] for x in tr.day_view(ali, today)['items']]
    assert titles == ['Забрать справку']
    assert [x['title'] for x in tr.day_view(ali, today + timedelta(days=1))['items']] == ['Спортзал']
    assert tr.set_value(ali, task, today) == 1
    with pytest.raises(tr.TrackerError):
        tr.create_habit(ali, {'title': 'x'})


def test_stats_for_charts(pair):
    ali = pair[0]
    today = timezone.localdate()
    h = tr.create_habit(ali, {'title': 'Чтение', 'kind': 'count', 'target': 10, 'unit': 'страниц'})
    Habit.objects.filter(pk=h.pk).update(start_on=today - timedelta(days=9))
    for i in range(5):
        HabitLog.objects.create(habit=h, user=ali, day=today - timedelta(days=i), value=10)
    HabitLog.objects.create(habit=h, user=ali, day=today - timedelta(days=6), value=4)       # не дотянул до цели
    s = tr.stats(ali, 7)
    assert len(s['days']) == 7 and s['done'] == 5 and s['total'] == 7 and s['rate'] == 71 and s['perfect_days'] == 5
    row = s['habits'][0]
    assert row['streak'] == 5 and row['sum'] == 54 and row['cells'][-5:] == [1, 1, 1, 1, 1]


def test_private_habits_are_private(pair, client):
    ali, umar, _z = pair
    h = tr.create_habit(ali, {'title': 'Личное'})
    with pytest.raises(tr.TrackerError):
        tr.get_habit(umar, h.pk)
    assert call(client, 'post', f'/api/v1/tracker/habits/{h.pk}/log/', umar).status_code == 404
    assert call(client, 'get', '/api/v1/tracker/', umar).json()['items'] == []
    client.force_login(umar)
    assert client.get(f'/tracker/h/{h.pk}/').status_code == 404
    assert client.post(f'/tracker/h/{h.pk}/log/').status_code == 404


def test_shared_board_and_competition(pair):
    ali, umar, zayd = pair
    today = timezone.localdate()
    board = tr.create_board(ali, 'Учим арабский', '📚')
    with pytest.raises(tr.TrackerError):
        tr.get_board(umar, board.pk)                                   # чужой трекер не виден
    tr.join(umar, board.invite_code)
    tr.join(zayd, board.invite_code)
    words = tr.create_habit(ali, {'title': '10 новых слов'}, board)
    listen = tr.create_habit(umar, {'title': 'Слушать урок'}, board)   # добавлять может любой участник
    Habit.objects.filter(board=board).update(start_on=today - timedelta(days=3))
    words.refresh_from_db()
    listen.refresh_from_db()
    tr.set_value(ali, words, today)
    tr.set_value(umar, words, today)
    tr.set_value(umar, listen, today)
    HabitLog.objects.create(habit=words, user=umar, day=today - timedelta(days=1), value=1)
    # у каждого свои отметки; общая привычка — в его «сегодня»
    assert [x['done'] for x in tr.day_view(zayd, today)['items']] == [False, False]
    view = tr.board_view(ali, board, today, 7)
    assert [p['done'] for p in view['items'][0]['who']] == [True, True, False]
    assert 'place' not in view['people'][0]                            # соревнование выключено — без мест
    tr.update_board(ali, board, {'compete': '1'})
    table = tr.board_view(ali, board, today, 7)['people']
    assert [(p['name'], p['points'], p['place']) for p in table] == [('Umar', 3, 1), ('Ali', 1, 2), ('Zayd', 0, 3)]
    # править общую привычку может автор и владелец трекера, чужой участник — нет
    with pytest.raises(tr.TrackerError):
        tr.update_habit(zayd, words, {'title': 'Взлом'})
    tr.update_habit(ali, listen, {'title': 'Слушать урок 15 минут'})
    with pytest.raises(tr.TrackerError):
        tr.update_board(umar, board, {'compete': ''})
    # вышел — отметки в этом трекере стёрты; владелец выйти не может
    tr.leave(umar, board)
    assert not HabitLog.objects.filter(user=umar).exists()
    with pytest.raises(tr.TrackerError):
        tr.leave(ali, board)
    old = board.invite_code
    tr.update_board(ali, board, {'new_link': '1'})
    board.refresh_from_db()
    with pytest.raises(tr.TrackerError):
        tr.join(umar, old)


def test_api_flow(pair, client):
    ali, umar, _z = pair
    r = call(client, 'post', '/api/v1/tracker/habits/new/', ali, {'title': 'Витамины', 'emoji': '💊', 'remind_at': '08:30', 'tz_offset': 300})
    assert r.status_code == 200
    hid = r.json()['id']
    day = call(client, 'get', '/api/v1/tracker/', ali).json()
    assert day['total'] == 1 and day['items'][0]['remind_at'] == '08:30' and len(day['week']) == 7
    assert call(client, 'post', f'/api/v1/tracker/habits/{hid}/log/', ali, {'day': day['day']}).json() == {'value': 1, 'done': True}
    assert call(client, 'get', '/api/v1/tracker/stats/', ali, {'days': 7}).json()['done'] == 1
    assert call(client, 'post', f'/api/v1/tracker/habits/{hid}/', ali, {'title': 'Витамин D', 'archived': '1'}).json()['archived'] is True
    assert call(client, 'get', '/api/v1/tracker/', ali).json()['items'] == []
    assert len(call(client, 'get', '/api/v1/tracker/habits/', ali).json()['items']) == 1
    # общий трекер по ссылке
    bid = call(client, 'post', '/api/v1/tracker/boards/new/', ali, {'title': 'Работа над сайтом', 'compete': '1'}).json()['id']
    board = call(client, 'get', f'/api/v1/tracker/boards/{bid}/', ali).json()
    code = board['invite_link'].rstrip('/').split('/')[-1]
    assert call(client, 'get', f'/api/v1/tracker/boards/{bid}/', umar).status_code == 404
    assert call(client, 'get', f'/api/v1/tracker/join/{code}/', umar).json()['member'] is False
    assert call(client, 'post', f'/api/v1/tracker/join/{code}/', umar).json()['member'] is True
    call(client, 'post', '/api/v1/tracker/habits/new/', umar, {'title': 'Закрыть задачу', 'board': bid})
    assert len(call(client, 'get', f'/api/v1/tracker/boards/{bid}/', ali).json()['items']) == 1
    assert call(client, 'post', f'/api/v1/tracker/boards/{bid}/', umar, {'leave': 1}).json()['left'] is True
    assert call(client, 'delete', f'/api/v1/tracker/boards/{bid}/', ali).status_code == 200
    assert call(client, 'delete', f'/api/v1/tracker/habits/{hid}/', ali).status_code == 200
    # раздел выключили в админке
    ModuleConfig.objects.filter(key='tracker').update(status='off')
    assert call(client, 'get', '/api/v1/tracker/', ali).status_code == 404


def test_site_pages(pair, client):
    ali, umar, _z = pair
    client.force_login(ali)
    assert 'Начните с одной привычки' in client.get('/tracker/').content.decode()
    r = client.post('/tracker/new/', {'title': 'Зарядка', 'emoji': '🏃', 'color': '#10b981', 'kind': 'check', 'repeat': 'days',
                                      'days': ['1', '2', '3', '4', '5', '6', '7'], 'remind_at': '', 'tz_offset': '300'})
    assert r.status_code == 302
    h = Habit.objects.get()
    html = client.get('/tracker/').content.decode()
    assert 'Зарядка' in html and '0 / 1' in html
    assert client.post(f'/tracker/h/{h.pk}/log/', {'day': timezone.localdate().isoformat()}).json() == {'value': 1, 'done': True, 'target': 1}
    assert '100%' in client.get('/tracker/').content.decode()
    assert 'По привычкам' in client.get('/tracker/stats/').content.decode()
    assert client.post('/tracker/b/new/', {'title': 'Семья', 'emoji': '🤝', 'compete': 'on'}).status_code == 302
    board = ali.tracker_boards.get()
    assert 'Таблица' in client.get(f'/tracker/b/{board.pk}/').content.decode()
    client.force_login(umar)
    assert client.get(f'/tracker/b/{board.pk}/').status_code == 404
    assert 'Присоединиться' in client.get(f'/tracker/join/{board.invite_code}/').content.decode()
    assert client.post(f'/tracker/join/{board.invite_code}/').status_code == 302
    assert client.get(f'/tracker/b/{board.pk}/').status_code == 200


def test_reminders(pair):
    ali = pair[0]
    now = timezone.now().replace(second=0, microsecond=0)
    local = now + timedelta(minutes=300)
    h = tr.create_habit(ali, {'title': 'Таблетки', 'remind_at': local.strftime('%H:%M'), 'tz_offset': 300})
    Habit.objects.filter(pk=h.pk).update(start_on=local.date() - timedelta(days=1))
    assert [(u.pk, x.pk) for u, x in tr.due_reminders(now)] == [(ali.pk, h.pk)]
    assert tr.due_reminders(now + timedelta(minutes=5)) == []
    from django.core.management import call_command
    call_command('tracker_remind')
    assert Notification.objects.filter(user=ali, text__contains='Таблетки').count() in (0, 1)   # минута могла смениться
    HabitLog.objects.create(habit=h, user=ali, day=local.date(), value=1)
    assert tr.due_reminders(now) == []                                 # уже сделал — не напоминаем
