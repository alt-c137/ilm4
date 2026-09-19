"""Расчёт времён намаза — локально, без внешних API (PASSPORT §6).

Библиотека praytimes — порт PrayTimes.org: астрономия по координатам и дате,
методы отличаются углами Фаджр/Иша. У всех вызовов один вход — compute().
"""
from datetime import date, datetime

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
    if method in pt.methods and method != 'MWL':
        pt.adjust(pt.methods[method]['params'])
    day = day or date.today()
    times = pt.getTimes((day.year, day.month, day.day), (lat, lon), tz_offset)
    return {key: times[key] for key in NAMES}


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
