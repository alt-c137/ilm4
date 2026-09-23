"""Оплаты: подписи провайдеров, сверка суммы, отсутствие двойного зачисления."""
import hashlib
import hmac
import json
import time

import pytest
from django.contrib.auth import get_user_model

from apps.payments.models import TopUp
from apps.wallet import services as wallet

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user('pay', 'pay@x.com', 'x')


# ---------- Click ----------
def _click(settings, t, action, prepare_id='', amount=None, **extra):
    p = {'click_trans_id': '111', 'service_id': '9', 'click_paydoc_id': '1', 'merchant_trans_id': str(t.pk),
         'amount': amount or f'{t.amount:.2f}', 'action': str(action), 'error': '0', 'error_note': 'ok',
         'sign_time': '2026-09-24 10:00:00', **extra}
    if prepare_id:
        p['merchant_prepare_id'] = prepare_id
    raw = f"111{p['service_id']}{settings.CLICK_SECRET_KEY}{t.pk}{prepare_id}{p['amount']}{action}{p['sign_time']}"
    p['sign_string'] = hashlib.md5(raw.encode()).hexdigest()
    return p


def test_click_prepare_complete(client, settings, user):
    settings.CLICK_SECRET_KEY = 'sk'
    t = TopUp.objects.create(user=user, amount=50_000, provider='click')
    r = client.post('/payments/click/prepare/', _click(settings, t, 0)).json()
    assert r['error'] == 0 and r['merchant_prepare_id'] == t.pk
    r = client.post('/payments/click/complete/', _click(settings, t, 1, prepare_id=str(t.pk))).json()
    assert r['error'] == 0 and wallet.balance_of(user) == 50_000
    r = client.post('/payments/click/complete/', _click(settings, t, 1, prepare_id=str(t.pk))).json()
    assert r['error'] == -4 and wallet.balance_of(user) == 50_000       # повтор — без зачисления


def test_click_rejects_bad_sign_and_amount(client, settings, user):
    settings.CLICK_SECRET_KEY = 'sk'
    t = TopUp.objects.create(user=user, amount=50_000, provider='click')
    bad = _click(settings, t, 0)
    bad['sign_string'] = 'x' * 32
    assert client.post('/payments/click/prepare/', bad).json()['error'] == -1
    assert client.post('/payments/click/prepare/', _click(settings, t, 0, amount='1.00')).json()['error'] == -2


# ---------- Stripe ----------
def test_stripe_webhook_signature(client, settings, user):
    settings.STRIPE_WEBHOOK_SECRET = 'whsec'
    t = TopUp.objects.create(user=user, amount=120_000, provider='stripe', external_id='cs_1')
    body = json.dumps({'type': 'checkout.session.completed', 'data': {'object': {
        'id': 'cs_1', 'client_reference_id': str(t.pk), 'payment_status': 'paid'}}}).encode()
    ts = str(int(time.time()))
    good = hmac.new(b'whsec', f'{ts}.'.encode() + body, hashlib.sha256).hexdigest()
    assert client.post('/payments/stripe/webhook/', body, content_type='application/json',
                       HTTP_STRIPE_SIGNATURE=f't={ts},v1={"0" * 64}').status_code == 400
    assert wallet.balance_of(user) == 0
    assert client.post('/payments/stripe/webhook/', body, content_type='application/json',
                       HTTP_STRIPE_SIGNATURE=f't={ts},v1={good}').status_code == 200
    assert wallet.balance_of(user) == 120_000


# ---------- NOWPayments ----------
def test_crypto_ipn_signature(client, settings, user):
    settings.NOWPAYMENTS_IPN_SECRET = 'ipn'
    t = TopUp.objects.create(user=user, amount=300_000, provider='crypto')
    body = {'payment_status': 'finished', 'order_id': str(t.pk), 'pay_amount': 23.5}
    sig = hmac.new(b'ipn', json.dumps(body, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha512).hexdigest()
    assert client.post('/payments/crypto/ipn/', json.dumps(body), content_type='application/json',
                       HTTP_X_NOWPAYMENTS_SIG='bad').status_code == 400
    assert client.post('/payments/crypto/ipn/', json.dumps(body), content_type='application/json',
                       HTTP_X_NOWPAYMENTS_SIG=sig).status_code == 200
    assert wallet.balance_of(user) == 300_000


# ---------- Telegram Stars ----------
def test_stars_flow(client, settings, user, monkeypatch):
    settings.TELEGRAM_BOT_TOKEN = '1:T'
    calls = []

    def fake(method, data=None, files=None, timeout=10):
        calls.append((method, data or {}))
        return 'https://t.me/$inv' if method == 'createInvoiceLink' else {'ok': True}
    for mod in ('apps.accounts.telegram', 'apps.payments.stars', 'apps.tgbot.dispatch'):
        monkeypatch.setattr(f'{mod}.api', fake, raising=False)
    user.telegram_id = 999
    user.save()
    client.force_login(user)
    j = client.post('/wallet/topup/', {'provider': 'stars', 'amount': '100000'}, HTTP_ACCEPT='application/json').json()
    assert j['ok'] and j['stars'] and j['url'] == 'https://t.me/$inv'
    t = TopUp.objects.get()
    stars = int(t.external_id.split(':')[1])        # 100 000 / 250 = 400 звёзд
    assert stars == 400
    from apps.tgbot.dispatch import handle_update
    handle_update({'update_id': 1, 'pre_checkout_query': {'id': 'pq', 'from': {'id': 999}, 'currency': 'XTR',
                                                         'total_amount': stars, 'invoice_payload': f'topup:{t.pk}'}})
    assert calls[-1] == ('answerPreCheckoutQuery', {'pre_checkout_query_id': 'pq', 'ok': 'true'})
    handle_update({'update_id': 2, 'message': {'message_id': 5, 'chat': {'id': 999, 'type': 'private'},
                                                'from': {'id': 999}, 'successful_payment': {
                                                    'currency': 'XTR', 'total_amount': stars,
                                                    'invoice_payload': f'topup:{t.pk}',
                                                    'telegram_payment_charge_id': 'ch1'}}})
    assert wallet.balance_of(user) == 100_000
    # чужой человек не может оплатить чужой счёт
    t2 = TopUp.objects.create(user=user, amount=1000, provider='stars', external_id='stars:4')
    handle_update({'update_id': 3, 'pre_checkout_query': {'id': 'pq2', 'from': {'id': 1}, 'currency': 'XTR',
                                                         'total_amount': 4, 'invoice_payload': f'topup:{t2.pk}'}})
    assert calls[-1][1]['ok'] == 'false'
