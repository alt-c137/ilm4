"""Telegram Stars: бот получает pre_checkout_query (проверить заказ за 10 с) и
successful_payment (оплачено — зачислить). Вызывается из apps.tgbot.dispatch."""
from apps.accounts.telegram import api

from .models import TopUp
from .services import mark_paid


def _topup(payload: str):
    if not payload.startswith('topup:') or not payload[6:].isdigit():
        return None
    return TopUp.objects.filter(pk=int(payload[6:]), provider='stars').select_related('user').first()


def pre_checkout(q: dict) -> None:
    t = _topup(q.get('invoice_payload', ''))
    ok = bool(t and t.status == TopUp.PENDING and q.get('currency') == 'XTR'
              and t.external_id == f"stars:{q.get('total_amount')}"
              and t.user.telegram_id == q.get('from', {}).get('id'))
    api('answerPreCheckoutQuery', {'pre_checkout_query_id': q['id'], 'ok': 'true' if ok else 'false',
                                   **({} if ok else {'error_message': 'Счёт устарел — создайте новый в приложении'})})


def success(msg: dict) -> None:
    sp = msg['successful_payment']
    t = _topup(sp.get('invoice_payload', ''))
    if not t or sp.get('currency') != 'XTR' or t.external_id != f"stars:{sp.get('total_amount')}":
        return
    if mark_paid(t):
        TopUp.objects.filter(pk=t.pk).update(external_id=f"stars:{sp.get('total_amount')}:"
                                                        f"{sp.get('telegram_payment_charge_id', '')}"[:120])
        api('sendMessage', {'chat_id': msg['chat']['id'],
                            'text': f'Баланс пополнен на {int(t.amount):,} сум. БаракаЛлаху фикум!'.replace(',', ' ')})
