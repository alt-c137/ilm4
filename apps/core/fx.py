"""Курсы валют и крипты для карточки «Сегодня».

Фиат — open.er-api.com (без ключа, обновляется раз в сутки), крипта — CoinGecko
(без ключа). Всё приводится к «единиц за 1 USD»; пересчёт в любую базовую валюту
делает браузер. Кэш в памяти процесса: 1 час; при сбое — повтор через 10 минут,
а до тех пор — запасной вариант из таблицы Rate (курсы ЦБ Узбекистана к суму).
"""
import time
from decimal import Decimal

import requests

FIAT_URL = 'https://open.er-api.com/v6/latest/USD'
CRYPTO_URL = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd'
TTL, RETRY = 3600, 600

# что предлагаем выбрать базой (порядок — в списке) и что показываем плитками
BASES = ['UZS', 'RUB', 'KZT', 'KGS', 'TJS', 'TRY', 'AED', 'SAR', 'EGP', 'EUR', 'GBP', 'USD']
SHOW = ['USD', 'EUR', 'RUB', 'BTC', 'GBP', 'TRY', 'AED']
NAMES = {
    'UZS': 'сум', 'RUB': 'рубль', 'KZT': 'тенге', 'KGS': 'сом', 'TJS': 'сомони', 'TRY': 'лира',
    'AED': 'дирхам', 'SAR': 'риял', 'EGP': 'ег. фунт', 'EUR': 'евро', 'GBP': 'фунт',
    'USD': 'доллар', 'BTC': 'биткоин', 'ETH': 'эфир',
}

_cache = {'data': None, 'ts': 0.0, 'ok': False}


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


def get_rates() -> dict:
    """{'rates': {код: единиц за 1 USD}, 'source': 'live'|'cbu', 'ts': unix}."""
    now = time.time()
    if _cache['data'] is not None and now - _cache['ts'] < (TTL if _cache['ok'] else RETRY):
        return _cache['data']
    rates, ok = {}, False
    try:
        r = requests.get(FIAT_URL, timeout=4, headers={'User-Agent': 'ilm4/1.0'}).json()
        if r.get('result') == 'success' and r.get('rates'):
            rates = {k: float(v) for k, v in r['rates'].items()}
            ok = True
    except (requests.RequestException, ValueError):
        pass
    if rates:
        try:
            c = requests.get(CRYPTO_URL, timeout=4, headers={'User-Agent': 'ilm4/1.0'}).json()
            for code, key in (('BTC', 'bitcoin'), ('ETH', 'ethereum')):
                usd = float(c.get(key, {}).get('usd') or 0)
                if usd:
                    rates[code] = 1 / usd
        except (requests.RequestException, ValueError):
            pass
    source = 'live'
    if not rates:
        rates, source = _fallback(), 'cbu'
    data = {'rates': {k: v for k, v in rates.items() if k in set(BASES) | set(SHOW) | {'ETH'}},
            'source': source, 'ts': int(now), 'bases': BASES, 'show': SHOW, 'names': NAMES}
    _cache.update(data=data, ts=now, ok=ok)
    return data
