"""Валюты: цена автора + «≈» в валюте посетителя, откуда берётся валюта по умолчанию."""
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory
from django.utils import timezone

from apps.core import fx, money

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def rates():
    import time
    cache.set(fx.CACHE_KEY, {'rates': {'USD': 1.0, 'UZS': 12500.0, 'RUB': 90.0, 'SAR': 3.75, 'UAH': 41.0, 'EUR': 0.9},
                             'source': 'live', 'ts': time.time(), 'ok': True}, 3600)
    fx.forget()
    yield
    cache.delete(fx.CACHE_KEY)
    fx.forget()


def _req(user=None, cookies=None, **headers):
    from django.contrib.auth.models import AnonymousUser
    r = RequestFactory().get('/', **headers)
    r.user = user or AnonymousUser()
    r.COOKIES.update(cookies or {})
    return r


def test_format_and_convert(rates):
    assert money.fmt(1200000, 'UZS') == '1 200 000 сум'
    assert money.fmt(95, 'USD') == '$95'
    assert money.fmt(1500, 'UAH') == '1 500 ₴'
    assert round(money.convert(1250000, 'UZS', 'USD')) == 100
    assert money.approx(1250000, 'UZS', _req(cookies={'ilm4_cur': 'USD'})) == '≈ $100'
    assert money.approx(100, 'USD', _req(cookies={'ilm4_cur': 'USD'})) == ''           # своя валюта — без «≈»
    assert money.price_text(100, 'USD', _req(cookies={'ilm4_cur': 'UZS'})) == '$100 · ≈ 1 250 000 сум'


def test_who_sees_which_currency(rates):
    """Сам выбрал → страна (Cloudflare / часовой пояс) → номер телефона → язык → настройка сайта."""
    u = User.objects.create_user('u', 'u@x.com', 'x', phone='+380501234567', phone_verified_at=timezone.now())
    assert money.viewer_currency(_req(u)) == 'UAH'                                      # по номеру
    assert money.viewer_currency(_req(u, HTTP_CF_IPCOUNTRY='SA')) == 'SAR'              # страна важнее номера
    assert money.viewer_currency(_req(u, cookies={'ilm4_cur_auto': 'RUB'})) == 'RUB'    # часовой пояс устройства
    u.currency = 'EUR'
    assert money.viewer_currency(_req(u, HTTP_CF_IPCOUNTRY='SA')) == 'EUR'              # выбрал сам — главнее всего
    assert money.viewer_currency(_req()) == 'USD'                                       # ничего не известно
    assert money.by_phone('+77011234567') == 'KZT' and money.by_phone('+79161234567') == 'RUB'


def test_currency_switch_saves_to_profile_and_listing_shows_approx(rates, client):
    from apps.core.models import Moderation, ModuleConfig
    from apps.market.models import Category, Listing
    ModuleConfig.objects.update_or_create(key='buy', defaults={'name': 'Маркет', 'status': 'on'})
    u = User.objects.create_user('u', 'u@x.com', 'x')
    cat = Category.objects.create(name='Разное', slug='misc')
    item = Listing.objects.create(title='Коврик', description='новый', price=1250000, currency='UZS', category=cat,
                                  city='Ташкент', owner=u, status=Moderation.APPROVED)
    client.force_login(u)
    assert client.post('/currency/', {'currency': 'USD'}).status_code == 302
    u.refresh_from_db()
    assert u.currency == 'USD'
    page = client.get(f'/buy/{item.pk}/').content.decode()
    assert '1 250 000 сум' in page and '≈ $100' in page
    client.post('/currency/', {'currency': 'auto'})
    u.refresh_from_db()
    assert u.currency == ''


def test_rates_never_block_the_page(settings, monkeypatch):
    """Нет курсов в кеше — страница не идёт в сеть: берём запасные из базы и обновляем в фоне."""
    from apps.core.models import Rate
    cache.delete(fx.CACHE_KEY)
    fx.forget()
    called = []
    monkeypatch.setattr(fx, 'fetch', lambda: called.append(1) or {})
    Rate.objects.update_or_create(code='USD', defaults={'rate': 12500})
    data = fx.get_rates()
    assert data['source'] == 'cbu' and data['rates']['UZS'] == 12500.0 and not called
    monkeypatch.setattr(fx, 'fetch', lambda: {'USD': 1.0, 'UZS': 12600.0})
    assert fx.refresh() is True
    assert fx.get_rates()['rates']['UZS'] == 12600.0
