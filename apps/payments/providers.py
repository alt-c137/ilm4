"""Платёжные способы пополнения баланса. Способ появляется, когда заданы его ключи.

    start(topup, request) -> URL оплаты (куда отправить человека)

Подтверждение оплаты приходит от провайдера на наш адрес (callbacks.py) и проверяется
подписью; только после этого деньги зачисляются (services.mark_paid, повтор не зачисляет).
Данные карт видит только провайдер — платформа их не получает.

| способ     | кому                     | ключи в .env                                   |
|------------|--------------------------|------------------------------------------------|
| stars      | Telegram Stars           | TELEGRAM_BOT_TOKEN (больше ничего)             |
| click      | Uzcard / Humo (Click)    | CLICK_SERVICE_ID, CLICK_MERCHANT_ID, CLICK_SECRET_KEY |
| stripe     | Visa / Mastercard, Apple/Google Pay | STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET |
| crypto     | USDT, BTC и др.          | NOWPAYMENTS_API_KEY, NOWPAYMENTS_IPN_SECRET    |
"""
import math
from decimal import Decimal
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy


class ProviderNotReady(Exception):
    pass


def _abs(request, name, *args):
    base = getattr(settings, 'SITE_URL', '').rstrip('/')
    path = reverse(name, args=args)
    return base + path if base else request.build_absolute_uri(path)


def usd_amount(amount_uzs) -> Decimal:
    """Сумма в сум → доллары по текущему курсу (для карт мира и крипты)."""
    from apps.core.fx import get_rates

    per_usd = Decimal(str(get_rates()['rates'].get('UZS') or 12_700))
    return max(Decimal('1.00'), (Decimal(amount_uzs) / per_usd).quantize(Decimal('0.01')))


class Provider:
    key = ''
    title = ''
    hint = ''
    icon = ''
    env_keys: tuple = ()

    @classmethod
    def ready(cls) -> bool:
        return bool(cls.env_keys) and all(getattr(settings, k, '') for k in cls.env_keys)

    def start(self, topup, request) -> str:
        raise ProviderNotReady(_('{v0}: не настроено').format(v0=self.title))


class Stars(Provider):
    """Telegram Stars: счёт в боте. Оплата подтверждается апдейтом successful_payment."""
    key, title, hint, icon = 'stars', 'Telegram Stars', _lazy('Звёзды Telegram — из приложения, в 2 касания'), 'star'
    env_keys = ('TELEGRAM_BOT_TOKEN',)

    @staticmethod
    def stars_for(amount) -> int:
        from apps.core.models import SiteSettings
        rate = SiteSettings.get_solo().stars_rate or 250
        return max(1, math.ceil(Decimal(amount) / rate))

    def start(self, topup, request) -> str:
        from apps.accounts.telegram import api

        stars = self.stars_for(topup.amount)
        link = api('createInvoiceLink', {
            'title': _('Пополнение баланса ilm4'), 'description': _('{v0:,} сум на баланс').format(v0=int(topup.amount)).replace(',', ' '),
            'payload': f'topup:{topup.pk}', 'currency': 'XTR', 'prices': [{'label': _('Пополнение'), 'amount': stars}]})
        if not link:
            raise ProviderNotReady(_('Telegram не создал счёт — проверьте токен бота'))
        topup.external_id = f'stars:{stars}'
        topup.save(update_fields=['external_id'])
        return link


class Click(Provider):
    """Click (Узбекистан): Uzcard, Humo. Подтверждение — Prepare/Complete на наш адрес."""
    key, title, hint, icon = 'click', 'Uzcard / Humo', _lazy('Через Click — карты Узбекистана'), 'card'
    env_keys = ('CLICK_SERVICE_ID', 'CLICK_MERCHANT_ID', 'CLICK_SECRET_KEY')

    def start(self, topup, request) -> str:
        return 'https://my.click.uz/services/pay?' + urlencode({
            'service_id': settings.CLICK_SERVICE_ID, 'merchant_id': settings.CLICK_MERCHANT_ID,
            'amount': f'{topup.amount:.2f}', 'transaction_param': topup.pk,
            'return_url': _abs(request, 'payments:done', topup.pk)})


class Stripe(Provider):
    """Stripe Checkout: Visa/Mastercard мира, Apple Pay, Google Pay. Сумма — в долларах по курсу."""
    key, title, hint, icon = 'stripe', _lazy('Карта мира'), _lazy('Visa, Mastercard, Apple Pay, Google Pay — через Stripe'), 'globe'
    env_keys = ('STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET')

    def start(self, topup, request) -> str:
        usd = usd_amount(topup.amount)
        try:
            r = requests.post('https://api.stripe.com/v1/checkout/sessions', auth=(settings.STRIPE_SECRET_KEY, ''),
                              timeout=15, data={
                                  'mode': 'payment', 'client_reference_id': str(topup.pk),
                                  'success_url': _abs(request, 'payments:done', topup.pk),
                                  'cancel_url': _abs(request, 'wallet:topup'),
                                  'line_items[0][quantity]': 1,
                                  'line_items[0][price_data][currency]': 'usd',
                                  'line_items[0][price_data][unit_amount]': int(usd * 100),
                                  'line_items[0][price_data][product_data][name]':
                                      _('Пополнение баланса ilm4: {v1} сум').format(v1=int(topup.amount))})
            data = r.json()
        except (requests.RequestException, ValueError):
            raise ProviderNotReady(_('Stripe недоступен, попробуйте позже')) from None
        if not data.get('url'):
            raise ProviderNotReady(_('Stripe отклонил запрос: ') + str(data.get('error', {}).get('message', '')))
        topup.external_id = data['id']
        topup.save(update_fields=['external_id'])
        return data['url']


class Crypto(Provider):
    """NOWPayments: USDT (TRC20/ERC20), BTC, ETH и др. Подтверждение — IPN с подписью."""
    key, title, hint, icon = 'crypto', _lazy('Криптовалюта'), _lazy('USDT, BTC, ETH — через NOWPayments'), 'coin'
    env_keys = ('NOWPAYMENTS_API_KEY', 'NOWPAYMENTS_IPN_SECRET')

    def start(self, topup, request) -> str:
        try:
            r = requests.post('https://api.nowpayments.io/v1/invoice', timeout=15,
                              headers={'x-api-key': settings.NOWPAYMENTS_API_KEY}, json={
                                  'price_amount': float(usd_amount(topup.amount)), 'price_currency': 'usd',
                                  'order_id': str(topup.pk), 'order_description': _('ilm4 пополнение #{v1}').format(v1=topup.pk),
                                  'ipn_callback_url': _abs(request, 'payments:crypto_ipn'),
                                  'success_url': _abs(request, 'payments:done', topup.pk),
                                  'cancel_url': _abs(request, 'wallet:topup')})
            data = r.json()
        except (requests.RequestException, ValueError):
            raise ProviderNotReady(_('Криптошлюз недоступен, попробуйте позже')) from None
        if not data.get('invoice_url'):
            raise ProviderNotReady(_('Криптошлюз отклонил запрос'))
        topup.external_id = str(data.get('id', ''))
        topup.save(update_fields=['external_id'])
        return data['invoice_url']


PROVIDERS = {p.key: p for p in (Stars, Click, Stripe, Crypto)}


def available():
    return [p for p in PROVIDERS.values() if p.ready()]
