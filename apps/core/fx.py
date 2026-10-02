"""Курсы валют и крипты: карточка «Сегодня» и пересчёт цен (apps/core/money.py).

Фиат — open.er-api.com (без ключа, обновляется раз в сутки), крипта — CoinGecko
(без ключа). Всё приводится к «единиц за 1 USD».

Страница никогда не ждёт чужой сервер: курсы лежат в общем кеше, устаревшие
обновляются в фоне (отдаём прежние и запускаем обновление), а совсем без данных —
запасной вариант из таблицы Rate. Плановое обновление — manage.py pull_rates.
"""
import threading
import time
from decimal import Decimal

import requests
from django.utils.translation import gettext_lazy as _lazy

FIAT_URL = 'https://open.er-api.com/v6/latest/USD'
CRYPTO_URL = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd'
TTL, RETRY = 3600, 600

# что предлагаем выбрать базой (порядок — в списке) и что показываем плитками
BASES = ['UZS', 'RUB', 'KZT', 'KGS', 'TJS', 'UAH', 'TRY', 'AED', 'SAR', 'EGP', 'EUR', 'GBP', 'USD']
SHOW = ['USD', 'EUR', 'RUB', 'BTC', 'GBP', 'TRY', 'AED']
NAMES = {
    'UZS': _lazy('сум'), 'RUB': _lazy('рубль'), 'KZT': _lazy('тенге'), 'KGS': _lazy('сом'), 'TJS': _lazy('сомони'), 'TRY': _lazy('лира'),
    'UAH': _lazy('гривна'),
    'AED': _lazy('дирхам'), 'SAR': _lazy('риял'), 'EGP': _lazy('ег. фунт'), 'EUR': _lazy('евро'), 'GBP': _lazy('фунт'),
    'USD': _lazy('доллар'), 'BTC': _lazy('биткоин'), 'ETH': _lazy('эфир'),
}

CACHE_KEY, KEEP = 'fx:rates:v2', 7 * 24 * 3600        # в общем кеше храним неделю — на случай долгого сбоя источника
_local = {'data': None, 'ts': 0.0}                    # копия в памяти процесса: не ходить в кеш на каждый запрос
_busy = threading.Lock()


def _fallback() -> dict:
    """Курсы ЦБ Узбекистана из БД (сум за единицу) → единиц за 1 USD."""
    from .models import Rate
    uzs = {r.code: Decimal(r.rate) for r in Rate.objects.all()}
    if not uzs.get('USD'):
        return {}
    usd = uzs['USD']
    rates = {'USD': 1.0, 'UZS': float(usd)}
    for code, val in uzs.items():
        if val:
            rates[code] = float(usd / val)
    return rates


def _pack(rates: dict, source: str, ts: float, ok: bool) -> dict:
    keep = set(BASES) | set(SHOW) | {'ETH'}
    return {'rates': {k: v for k, v in rates.items() if k in keep}, 'source': source, 'ts': int(ts), 'ok': ok,
            'bases': BASES, 'show': SHOW, 'names': NAMES}


def fetch() -> dict:
    """Сходить к источникам (сеть!). Только из фона или команды, не из запроса страницы."""
    rates = {}
    try:
        r = requests.get(FIAT_URL, timeout=6, headers={'User-Agent': 'ilm4/1.0'}).json()
        if r.get('result') == 'success' and r.get('rates'):
            rates = {k: float(v) for k, v in r['rates'].items()}
    except (requests.RequestException, ValueError):
        pass
    if rates:
        try:
            c = requests.get(CRYPTO_URL, timeout=6, headers={'User-Agent': 'ilm4/1.0'}).json()
            for code, key in (('BTC', 'bitcoin'), ('ETH', 'ethereum')):
                usd = float(c.get(key, {}).get('usd') or 0)
                if usd:
                    rates[code] = 1 / usd
        except (requests.RequestException, ValueError):
            pass
    return rates


def refresh() -> bool:
    """Обновить курсы и положить в кеш. True — источник ответил."""
    from django.core.cache import cache
    now = time.time()
    rates = fetch()
    if rates:
        raw = {'rates': rates, 'source': 'live', 'ts': now, 'ok': True}
    else:                                              # источник молчит: помечаем попытку, чтобы не долбить его
        old = cache.get(CACHE_KEY) or {}
        raw = {'rates': old.get('rates') or {}, 'source': old.get('source', 'live'), 'ts': now - TTL + RETRY, 'ok': False}
    cache.set(CACHE_KEY, raw, KEEP)
    _local.update(data=None, ts=0.0)
    return bool(rates)


def _refresh_in_background() -> None:
    def run():
        from django.db import connection
        try:
            refresh()
        finally:
            connection.close()
            _busy.release()
    if _busy.acquire(blocking=False):
        threading.Thread(target=run, daemon=True).start()


def get_rates() -> dict:
    """{'rates': {код: единиц за 1 USD}, 'source': 'live'|'cbu', 'ts': unix}. Сеть не трогает."""
    from django.conf import settings
    from django.core.cache import cache
    now = time.time()
    if _local['data'] is not None and now - _local['ts'] < 60:
        return _local['data']
    raw = cache.get(CACHE_KEY)
    if (raw is None or now - raw['ts'] > TTL) and getattr(settings, 'FX_AUTO_REFRESH', True):
        _refresh_in_background()                       # отдаём то, что есть, свежее появится через пару секунд
    if raw and raw.get('rates'):
        data = _pack(raw['rates'], raw.get('source', 'live'), raw['ts'], True)
    else:
        data = _pack(_fallback(), 'cbu', now, False)
    _local.update(data=data, ts=now)
    return data


def forget() -> None:
    """Сбросить копию в памяти (тесты, после ручного обновления)."""
    _local.update(data=None, ts=0.0)
