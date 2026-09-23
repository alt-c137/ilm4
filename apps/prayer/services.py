"""Расчёт времён намаза — локально, без внешних API (PASSPORT §6).

Библиотека praytimes — порт PrayTimes.org: астрономия по координатам и дате,
методы отличаются углами Фаджр/Иша. У всех вызовов один вход — compute().
"""
from datetime import date, datetime, timedelta, timezone

from django.utils import timezone as dj_tz
from praytimes import PrayTimes

from .cities import CITIES, DEFAULT_CITY

# Методы расчёта: углы Фаджр/Иша (паспорт: метод — настройка, дефолт по региону)
METHODS = {
    'Karachi': 'Университет Карачи — СНГ, Азия (по умолчанию)',
    'MWL': 'Всемирная исламская лига — Европа, часть Азии',
    'ISNA': 'ISNA — Северная Америка',
    'Makkah': 'Умм аль-Кура — Саудовская Аравия',
    'Egypt': 'Египетский орган — Африка, Левант',
}
DEFAULT_METHOD = 'Karachi'

# Пять намазов + восход (восход — не намаз, но нужен в расписании)
NAMES = {
    'fajr': 'Фаджр', 'sunrise': 'Восход', 'dhuhr': 'Зухр',
    'asr': 'Аср', 'maghrib': 'Магриб', 'isha': 'Иша',
}
PRAYER_ONLY = ('fajr', 'dhuhr', 'asr', 'maghrib', 'isha')


def compute(lat: float, lon: float, tz_offset: int, day: date | None = None,
            method: str = DEFAULT_METHOD) -> dict[str, str]:
    """Времена на день: {'fajr': '04:34', ...} в местном времени координат."""
    pt = PrayTimes()
    if method == 'Makkah':
        # Умм аль-Кура: Фаджр 18.5°, Иша = Магриб + 90 мин.
        # Порт praytimes не умеет '90 min' (получалась Иша ДО Магриба) — считаем сами.
        pt.adjust({'fajr': 18.5})
    elif method in pt.methods and method != 'MWL':
        pt.adjust(pt.methods[method]['params'])
    day = day or date.today()
    times = pt.getTimes((day.year, day.month, day.day), (lat, lon), tz_offset)
    if method == 'Makkah':
        h, m = times['maghrib'].split(':')
        total = (int(h) * 60 + int(m) + 90) % 1440
        times['isha'] = f'{total // 60:02d}:{total % 60:02d}'
    return {key: times[key] for key in NAMES}


def local_now(tz_offset: float | None = None) -> datetime:
    """Текущее время (наивное) в зоне города: UTC + смещение.
    Без смещения — зона проекта."""
    if tz_offset is None:
        return _now_naive()
    return dj_tz.now().astimezone(timezone.utc).replace(tzinfo=None) + timedelta(hours=tz_offset)


def next_epoch(times: dict[str, str], now: datetime | None = None,
               tz_offset: float | None = None) -> int:
    """Unix-время следующего намаза — для живого отсчёта на клиенте."""
    now = now or local_now(tz_offset)
    info = until_next(times, now)
    h, m = map(int, times[info['key']].split(':'))
    base = now.date()
    if info['tomorrow']:
        base = base + timedelta(days=1)
    tzinfo = (timezone(timedelta(hours=tz_offset)) if tz_offset is not None
              else dj_tz.get_default_timezone())
    aware = datetime.combine(base, datetime.min.time()).replace(hour=h, minute=m, tzinfo=tzinfo)
    return int(aware.timestamp())


def compute_for_city(city_key: str, day: date | None = None,
                     method: str = DEFAULT_METHOD) -> dict[str, str]:
    _, lat, lon, tz = CITIES.get(city_key, CITIES[DEFAULT_CITY])
    return compute(lat, lon, tz, day=day, method=method)


def next_prayer(times: dict[str, str], now: datetime | None = None, tz_offset: int = 5):
    """Какой намаз ближайший: (ключ, название, 'осталось HH:MM' или 'завтра').

    now — текущее время в зоне координат (по умолчанию зона проекта).
    """
    now = now or _now_naive()
    prayer_times = [(k, datetime.strptime(times[k], '%H:%M')) for k in PRAYER_ONLY]
    for key, moment in prayer_times:
        if moment > now:
            delta = moment - now
            hours, rest = divmod(int(delta.total_seconds()), 3600)
            return key, NAMES[key], f'{hours}:{rest % 3600 // 60:02d}'
    return 'fajr', NAMES['fajr'], 'завтра'


def _now_naive() -> datetime:
    """Текущее время в зоне проекта (Asia/Tashkent), наивное.

    Нельзя брать datetime.now() напрямую: системные часы WSL могут стоять
    в другой зоне — и подсветка намаза поедет на часы.
    """
    return dj_tz.localtime().replace(tzinfo=None)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(':')
    return int(h) * 60 + int(m)


def _fmt_delta(minutes: int) -> str:
    minutes = max(1, minutes)
    if minutes < 60:
        return f'{minutes} мин'
    h, m = divmod(minutes, 60)
    return f'{h} ч {m:02d} мин'


def until_next(times: dict[str, str], now: datetime | None = None) -> dict:
    """Сколько осталось до следующего намаза (сегодня или завтра — честно).

    Возвращает {'key','name','time','human','tomorrow'}:
    human — «2 ч 14 мин», tomorrow — True, если следующий намаз завтра.
    """
    now = now or _now_naive()
    now_m = now.hour * 60 + now.minute
    marks = [(k, _minutes(times[k])) for k in PRAYER_ONLY]
    for key, moment in marks:
        if moment > now_m:
            return {'key': key, 'name': NAMES[key], 'time': times[key],
                    'human': _fmt_delta(moment - now_m), 'tomorrow': False}
    fajr = _minutes(times['fajr'])
    return {'key': 'fajr', 'name': NAMES['fajr'], 'time': times['fajr'],
            'human': _fmt_delta((1440 - now_m) + fajr), 'tomorrow': True}


def prayer_progress(times: dict[str, str], now: datetime | None = None) -> int:
    """Процент (0–100) пути от предыдущего намаза к следующему — для полосы."""
    now = now or _now_naive()
    now_m = now.hour * 60 + now.minute
    marks = [(k, _minutes(times[k])) for k in PRAYER_ONLY]

    for i, (key, moment) in enumerate(marks):
        if moment > now_m:
            if i == 0:  # до Фаджра: интервал «вчера Иша → сегодня Фаджр»
                prev = marks[-1][1] - 1440
            else:
                prev = marks[i - 1][1]
            span = moment - prev
            return max(0, min(100, round((now_m - prev) / span * 100)))
    # после Иши: интервал «Иша → завтрашний Фаджр»
    isha, fajr = marks[-1][1], marks[0][1]
    span = (fajr + 1440) - isha
    return max(0, min(100, round((now_m - isha) / span * 100)))


def current_prayer(times: dict[str, str], now: datetime | None = None) -> str:
    """Текущий период: последний наступивший пункт расписания (включая восход).

    До Фаджра — ещё идёт вчерашний Иша. Восход — не намаз, но это граница
    времени Фаджра: после него «сейчас» показывается как «Восход».
    """
    now = now or _now_naive()
    now_m = now.hour * 60 + now.minute
    current = 'isha'
    for key in NAMES:
        if _minutes(times[key]) <= now_m:
            current = key
    return current


def schedule(times: dict[str, str], now: datetime | None = None) -> dict:
    """Расписание дня для шаблонов: пункты с флагами current / next / passed
    + текущий и следующий намаз с отсчётом."""
    now = now or _now_naive()
    now_m = now.hour * 60 + now.minute
    cur = current_prayer(times, now)
    until = until_next(times, now)
    items = []
    for key, label in NAMES.items():
        is_cur = key == cur
        items.append({
            'key': key, 'label': label, 'time': times[key],
            'current': is_cur,
            'next': key == until['key'],
            # «прошёл» — наступил сегодня и уже не текущий
            'passed': (not is_cur and _minutes(times[key]) <= now_m),
            'soon': key == until['key'] and not until['tomorrow'],
        })
    return {
        'items': items,
        'current_key': cur, 'current_name': NAMES[cur], 'current_time': times[cur],
        'next_key': until['key'], 'next_name': until['name'], 'next_time': until['time'],
        'until': until,
    }
