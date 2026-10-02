"""Валюты и цены — одно место для всего сайта и приложения.

Как у больших площадок: автор указывает цену в СВОЕЙ валюте (она и хранится),
а каждый посетитель видит рядом «≈ в своей». Своя валюта определяется так:

1. человек выбрал сам (профиль или кука — «Настройки» на сайте и в приложении);
2. страна по адресу в сети (заголовок CF-IPCountry от Cloudflare) или по часовому поясу
   устройства (кука ilm4_cur_auto — её ставит static/js/app.js);
3. код страны в подтверждённом номере телефона;
4. язык интерфейса (узбекский → сум);
5. валюта по умолчанию из «Настроек сайта».

Курсы — apps/core/fx.py (обновляются в фоне, запрос страницы их не ждёт).
"""
from decimal import Decimal, InvalidOperation

from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _lazy

# код, название для списка, знак, знак перед числом?
_ALL = [
    ('UZS', _lazy('сум'), _lazy('сум'), False),
    ('USD', _lazy('доллар'), '$', True),
    ('EUR', _lazy('евро'), '€', False),
    ('RUB', _lazy('рубль'), '₽', False),
    ('KZT', _lazy('тенге'), '₸', False),
    ('KGS', _lazy('сом'), _lazy('сом'), False),
    ('TJS', _lazy('сомони'), _lazy('сомони'), False),
    ('UAH', _lazy('гривна'), '₴', False),
    ('TRY', _lazy('лира'), '₺', False),
    ('SAR', _lazy('риял'), _lazy('риял'), False),
    ('AED', _lazy('дирхам'), _lazy('дирхам'), False),
    ('EGP', _lazy('ег. фунт'), _lazy('ег. фунт'), False),
    ('GBP', _lazy('фунт'), '£', True),
]
CODES = [c for c, *_ in _ALL]
NAME = {c: n for c, n, _s, _p in _ALL}
SIGN = {c: s for c, _n, s, _p in _ALL}
PREFIX = {c for c, _n, _s, p in _ALL if p}
# для полей моделей и форм: «UZS — сум»
CHOICES = [(c, format_lazy('{} — {}', c, n)) for c, n, _s, _p in _ALL]
COOKIE, COOKIE_AUTO = 'ilm4_cur', 'ilm4_cur_auto'

_EURO = ['AT', 'BE', 'CY', 'DE', 'EE', 'ES', 'FI', 'FR', 'GR', 'HR', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT', 'NL', 'PT', 'SI', 'SK']
COUNTRY = {'UZ': 'UZS', 'RU': 'RUB', 'BY': 'RUB', 'KZ': 'KZT', 'KG': 'KGS', 'TJ': 'TJS', 'UA': 'UAH', 'TR': 'TRY',
           'SA': 'SAR', 'AE': 'AED', 'EG': 'EGP', 'GB': 'GBP', 'US': 'USD', **{c: 'EUR' for c in _EURO}}
# код страны в номере (длинные — раньше коротких: +7 7xx — Казахстан, +7 — Россия)
PHONE = [('998', 'UZS'), ('996', 'KGS'), ('992', 'TJS'), ('380', 'UAH'), ('966', 'SAR'), ('971', 'AED'),
         ('77', 'KZT'), ('76', 'KZT'), ('90', 'TRY'), ('20', 'EGP'), ('44', 'GBP'), ('49', 'EUR'), ('33', 'EUR'),
         ('39', 'EUR'), ('34', 'EUR'), ('31', 'EUR'), ('32', 'EUR'), ('43', 'EUR'), ('7', 'RUB'), ('1', 'USD')]
LANG = {'uz': 'UZS'}


def by_phone(phone: str) -> str:
    digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
    return next((cur for prefix, cur in PHONE if digits.startswith(prefix)), '') if len(digits) >= 9 else ''


def site_default() -> str:
    from .models import SiteSettings
    code = SiteSettings.get_solo().default_currency
    return code if code in SIGN else 'USD'


def viewer_currency(request) -> str:
    """Валюта, в которой человеку показывать «≈» и подставлять в формы."""
    if request is None:
        return site_default()
    cached = getattr(request, '_ilm4_currency', None)
    if cached:
        return cached
    user = getattr(request, 'user', None)
    authed = bool(user is not None and user.is_authenticated)
    code = ''
    if authed and user.currency in SIGN:
        code = user.currency
    if not code and request.COOKIES.get(COOKIE) in SIGN:
        code = request.COOKIES[COOKIE]
    if not code and request.headers.get('X-Currency') in SIGN:         # приложение: выбор гостя на телефоне
        code = request.headers['X-Currency']
    if not code:
        code = COUNTRY.get((request.headers.get('CF-IPCountry') or '').upper(), '')
    if not code and request.COOKIES.get(COOKIE_AUTO) in SIGN:
        code = request.COOKIES[COOKIE_AUTO]
    if not code and authed and user.phone_verified:
        code = by_phone(user.phone)
    if not code:
        from django.utils.translation import get_language
        code = LANG.get((get_language() or '')[:2], '')
    code = code or site_default()
    request._ilm4_currency = code
    return code


def convert(amount, src: str, dst: str):
    """Пересчитать по текущему курсу. None — курса нет (сеть ещё не ответила)."""
    from .fx import get_rates
    rates = get_rates()['rates']
    if src == dst:
        return Decimal(str(amount))
    a, b = rates.get(src), rates.get(dst)
    if not a or not b:
        return None
    try:
        return Decimal(str(amount)) / Decimal(str(a)) * Decimal(str(b))
    except (InvalidOperation, ZeroDivisionError):
        return None


def _round(x: Decimal) -> Decimal:
    """«≈» — приблизительно: три значащие цифры для больших сумм, копейки — только для маленьких."""
    if x >= 1000:
        digits = len(str(int(x)))
        step = Decimal(10) ** (digits - 3)
        return (x / step).quantize(Decimal(1)) * step
    if x >= 10:
        return x.quantize(Decimal(1))
    return x.quantize(Decimal('0.01'))


def fmt(amount, code: str) -> str:
    """1200000, 'UZS' → «1 200 000 сум»; 95, 'USD' → «$95»."""
    try:
        x = Decimal(str(amount))
    except InvalidOperation:
        return ''
    text = f'{x:,.2f}' if x != x.to_integral_value() else f'{int(x):,}'
    text = text.replace(',', ' ')
    sign = str(SIGN.get(code, code))
    return f'{sign}{text}' if code in PREFIX else f'{text} {sign}'


def approx(amount, code: str, request) -> str:
    """«≈ $95» в валюте посетителя; пусто — валюта та же или курса нет."""
    dst = viewer_currency(request)
    if not amount or dst == code:
        return ''
    val = convert(amount, code, dst)
    if val is None or val <= 0:
        return ''
    return '≈ ' + fmt(_round(val), dst)


def price_text(amount, code: str, request=None, free='') -> str:
    """Цена одной строкой для API и карточек: «1 200 000 сум · ≈ $95»."""
    if not amount:
        return str(free)
    base = fmt(amount, code)
    extra = approx(amount, code, request) if request is not None else ''
    return f'{base} · {extra}' if extra else base


def choices_json() -> list:
    return [{'code': c, 'name': str(NAME[c]), 'sign': str(SIGN[c])} for c in CODES]
