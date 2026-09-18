"""Расчёт времён намаза — локально, без внешних API (PASSPORT §6).

Библиотека praytimes — порт PrayTimes.org: астрономия по координатам и дате,
методы отличаются углами Фаджр/Иша. У всех вызовов один вход — compute().
"""
from datetime import date, datetime

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
    now = now or datetime.now()
    prayer_times = [(k, datetime.strptime(times[k], '%H:%M')) for k in PRAYER_ONLY]
    for key, moment in prayer_times:
        if moment > now:
            delta = moment - now
            hours, rest = divmod(int(delta.total_seconds()), 3600)
            return key, NAMES[key], f'{hours}:{rest % 3600 // 60:02d}'
    return 'fajr', NAMES['fajr'], 'завтра'
