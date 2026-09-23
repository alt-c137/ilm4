"""Платёжные провайдеры. Новый способ оплаты = новый класс + ключи в .env.

Интерфейс:
    start(topup, request) -> URL страницы оплаты у провайдера
    parse_webhook(request) -> (external_id, paid: bool)   # с проверкой подписи провайдера

Сейчас провайдеры-заготовки: включаются, когда заданы ключи
(PAYME_*, CLICK_*, STRIPE_*, CRYPTO_*). Карточные данные хранит провайдер
(PCI DSS), платформа их не видит.
"""
from django.conf import settings


class ProviderNotReady(Exception):
    pass


class Provider:
    key = ''
    title = ''
    hint = ''
    env_keys: tuple = ()

    @classmethod
    def ready(cls) -> bool:
        return bool(cls.env_keys) and all(getattr(settings, k, '') for k in cls.env_keys)

    def start(self, topup, request) -> str:
        raise ProviderNotReady(f'{self.title}: подключение в работе')

    def parse_webhook(self, request):
        raise ProviderNotReady(f'{self.title}: подключение в работе')


class CardUZ(Provider):
    key, title, hint = 'card_uz', 'Карта Узбекистана', 'Uzcard, Humo — через Payme / Click'
    env_keys = ('PAYME_MERCHANT_ID', 'PAYME_SECRET')


class CardIntl(Provider):
    key, title, hint = 'card_intl', 'Банковская карта', 'Visa, Mastercard — через Stripe'
    env_keys = ('STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET')


class Crypto(Provider):
    key, title, hint = 'crypto', 'Криптовалюта', 'USDT, BTC — через криптошлюз'
    env_keys = ('CRYPTO_GATEWAY_KEY', 'CRYPTO_GATEWAY_SECRET')


PROVIDERS = {p.key: p for p in (CardUZ, CardIntl, Crypto)}


def available():
    return [p for p in PROVIDERS.values() if p.ready()]
