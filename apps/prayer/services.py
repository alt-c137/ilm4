"""Расчёт времён намаза — локально, без внешних API (PASSPORT §6).

Библиотека praytimes — порт PrayTimes.org: астрономия по координатам и дате,
методы отличаются углами Фаджр/Иша. У всех вызовов один вход — compute().
"""
from datetime import date, datetime, timedelta, timezone

from django.utils import timezone as dj_tz
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from praytimes import PrayTimes

from .cities import CITIES, DEFAULT_CITY

# Методы расчёта: углы Фаджр/Иша (паспорт: метод — настройка, дефолт по региону)
METHODS = {
    'Karachi': _lazy('Университет Карачи — СНГ, Азия (по умолчанию)'),
    'MWL': _lazy('Всемирная исламская лига — Европа, часть Азии'),
    'ISNA': _lazy('ISNA — Северная Америка'),
    'Makkah': _lazy('Умм аль-Кура — Саудовская Аравия'),
    'Egypt': _lazy('Египетский орган — Африка, Левант'),
}
DEFAULT_METHOD = 'Karachi'

# Пять намазов + восход (восход — не намаз, но нужен в расписании)
NAMES = {
    'fajr': _lazy('Фаджр'), 'sunrise': _lazy('Восход'), 'dhuhr': _lazy('Зухр'),
    'asr': _lazy('Аср'), 'maghrib': _lazy('Магриб'), 'isha': _lazy('Иша'),
}
PRAYER_ONLY = ('fajr', 'dhuhr', 'asr', 'maghrib', 'isha')


# углы Фаджр / Иша по методам. Иша у Умм аль-Кура — Магриб + 90 минут.
METHOD_PARAMS = {
    'Karachi': {'fajr': 18, 'isha': 18},
    'MWL': {'fajr': 18, 'isha': 17},
    'ISNA': {'fajr': 15, 'isha': 15},
    'Makkah': {'fajr': 18.5, 'isha': 18},   # Иша считаем сами ниже: в библиотеке «90 min» вычитается
    'Egypt': {'fajr': 19.5, 'isha': 17.5},
}


def compute(lat: float, lon: float, tz_offset: int, day: date | None = None,
            method: str = DEFAULT_METHOD, asr: str = 'Standard') -> dict[str, str]:
    """Времена на день: {'fajr': '04:34', ...} в местном времени координат.

    Все параметры задаются явно на каждый расчёт: в библиотеке praytimes настройки —
    общий для всех объектов словарь, а метод по умолчанию из-за её ошибки — шиитский
    «Джафари» (Магриб через 4° после заката). Без явных параметров MWL и Умм аль-Кура
    считались с этими остатками. Тот же расчёт — в приложении (mobile/src/lib/prayer.ts).
    """
    pt = PrayTimes()
    pt.settings = {'imsak': '10 min', 'dhuhr': '0 min', 'asr': asr, 'highLats': 'NightMiddle',
                   'maghrib': '0 min', 'midnight': 'Standard',
                   **METHOD_PARAMS.get(method, METHOD_PARAMS[DEFAULT_METHOD])}
    pt.offset = dict.fromkeys(pt.timeNames, 0)
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
    _name, lat, lon, tz = CITIES.get(city_key, CITIES[DEFAULT_CITY])
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
    return 'fajr', NAMES['fajr'], _('завтра')


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
        return _('{minutes} мин').format(minutes=minutes)
    h, m = divmod(minutes, 60)
    return _('{h} ч {m:02d} мин').format(h=h, m=m)


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
