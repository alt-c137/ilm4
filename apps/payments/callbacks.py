"""Подтверждения оплаты от провайдеров. Каждое проверяется подписью; сумма сверяется
с заказом; повторное подтверждение не зачисляет деньги второй раз (services.mark_paid)."""
import hashlib
import hmac
import json
import time
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import TopUp
from .services import mark_paid

# ---------- Click (Узбекистан) ----------
# Документация Click Shop API: два запроса — Prepare (action=0) и Complete (action=1).
CLICK_OK, CLICK_SIGN, CLICK_AMOUNT, CLICK_ACTION, CLICK_PAID, CLICK_NO_ORDER, CLICK_NO_TX, CLICK_CANCEL = \
    0, -1, -2, -3, -4, -5, -6, -9


def _click_sign(p, prepare_id='') -> str:
    raw = (f"{p.get('click_trans_id', '')}{p.get('service_id', '')}{settings.CLICK_SECRET_KEY}"
           f"{p.get('merchant_trans_id', '')}{prepare_id}{p.get('amount', '')}{p.get('action', '')}"
           f"{p.get('sign_time', '')}")
    return hashlib.md5(raw.encode()).hexdigest()


def _click(p, error, note, **extra):
    return JsonResponse({'click_trans_id': p.get('click_trans_id'), 'merchant_trans_id': p.get('merchant_trans_id'),
                         'error': error, 'error_note': note, **extra})


def _click_check(p, prepare_id=''):
    if not settings.CLICK_SECRET_KEY or not hmac.compare_digest(_click_sign(p, prepare_id), p.get('sign_string', '')):
        return None, _click(p, CLICK_SIGN, 'SIGN CHECK FAILED')
    t = TopUp.objects.filter(pk=p.get('merchant_trans_id') if str(p.get('merchant_trans_id', '')).isdigit() else 0,
                             provider='click').first()
    if not t:
        return None, _click(p, CLICK_NO_ORDER, 'Order not found')
    try:
        if Decimal(p.get('amount', '0')) != t.amount:
            return None, _click(p, CLICK_AMOUNT, 'Incorrect amount')
    except InvalidOperation:
        return None, _click(p, CLICK_AMOUNT, 'Incorrect amount')
    if t.status == TopUp.PAID:
        return None, _click(p, CLICK_PAID, 'Already paid')
    if t.status in (TopUp.CANCELLED, TopUp.FAILED):
        return None, _click(p, CLICK_CANCEL, 'Transaction cancelled')
    return t, None


@csrf_exempt
@require_POST
def click_prepare(request):
    p = request.POST
    if p.get('action') != '0':
        return _click(p, CLICK_ACTION, 'Action not found')
    t, err = _click_check(p)
    if err:
        return err
    t.external_id = f"click:{p.get('click_trans_id')}"
    t.save(update_fields=['external_id'])
    return _click(p, CLICK_OK, 'Success', merchant_prepare_id=t.pk)


@csrf_exempt
@require_POST
def click_complete(request):
    p = request.POST
    if p.get('action') != '1':
        return _click(p, CLICK_ACTION, 'Action not found')
    t, err = _click_check(p, p.get('merchant_prepare_id', ''))
    if err:
        return err
    if str(t.pk) != p.get('merchant_prepare_id'):
        return _click(p, CLICK_NO_TX, 'Transaction not found')
    if p.get('error', '0') != '0':          # Click сообщает об ошибке оплаты — отменяем заказ
        t.status = TopUp.CANCELLED
        t.save(update_fields=['status'])
        return _click(p, CLICK_CANCEL, 'Transaction cancelled')
    mark_paid(t)
    return _click(p, CLICK_OK, 'Success', merchant_confirm_id=t.pk)


# ---------- Stripe ----------
@csrf_exempt
@require_POST
def stripe_webhook(request):
    secret = settings.STRIPE_WEBHOOK_SECRET
    header = dict(part.split('=', 1) for part in request.headers.get('Stripe-Signature', '').split(',') if '=' in part)
    ts, sig = header.get('t', ''), header.get('v1', '')
    if not (secret and ts.isdigit() and sig):
        return HttpResponse(status=400)
    expected = hmac.new(secret.encode(), f'{ts}.'.encode() + request.body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig) or abs(time.time() - int(ts)) > 600:
        return HttpResponse(status=400)
    event = json.loads(request.body)
    obj = event.get('data', {}).get('object', {})
    if event.get('type') == 'checkout.session.completed' and obj.get('payment_status') == 'paid':
        t = TopUp.objects.filter(pk=obj.get('client_reference_id') or 0, provider='stripe',
                                 external_id=obj.get('id')).first()
        if t:
            mark_paid(t)
    return HttpResponse('ok')


# ---------- NOWPayments (крипта) ----------
@csrf_exempt
@require_POST
def crypto_ipn(request):
    secret = settings.NOWPAYMENTS_IPN_SECRET
    try:
        body = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)
    canon = json.dumps(body, sort_keys=True, separators=(',', ':'))
    expected = hmac.new(secret.encode(), canon.encode(), hashlib.sha512).hexdigest() if secret else ''
    if not expected or not hmac.compare_digest(expected, request.headers.get('x-nowpayments-sig', '')):
        return HttpResponse(status=400)
    if body.get('payment_status') == 'finished':
        t = TopUp.objects.filter(pk=body.get('order_id') if str(body.get('order_id', '')).isdigit() else 0,
                                 provider='crypto').first()
        if t and _crypto_full(t, body):
            mark_paid(t)
    return HttpResponse('ok')


def _num(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _crypto_full(topup, body) -> bool:
    """Оплачено ли пополнение целиком. Подпись говорит лишь, что письмо от NOWPayments; здесь сверяем, что оно
    про НАШ счёт на ЭТУ сумму и что прислали не меньше запрошенного. Недоплата обычно приходит со статусом
    partially_paid, но на один статус не полагаемся — зачисляем деньги, только когда сошлось всё."""
    import logging

    from .providers import usd_amount
    invoice = str(body.get('invoice_id') or '')
    price, want, got = _num(body.get('price_amount')), _num(body.get('pay_amount')), _num(body.get('actually_paid'))
    ok = not (topup.external_id and invoice and invoice != topup.external_id)        # платёж по другому счёту
    ok = ok and price is not None and str(body.get('price_currency', '')).lower() == 'usd'
    # счёт выставлен в долларах по курсу на момент создания; пока человек платил, курс мог чуть сдвинуться — но не на 10%
    ok = ok and price >= usd_amount(topup.amount) * Decimal('0.9')
    ok = ok and not (want is not None and got is not None and got < want * Decimal('0.99'))   # прислали меньше запрошенного
    if not ok:
        logging.getLogger(__name__).warning('NOWPayments: пополнение #%s не зачислено — сумма или счёт не сходятся: %s',
                                            topup.pk, {k: body.get(k) for k in ('invoice_id', 'price_amount', 'price_currency',
                                                                               'pay_amount', 'actually_paid')})
    return bool(ok)
