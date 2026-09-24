"""Кошелёк пользователя: баланс, история, заявка на вывод."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from apps.core.decorators import module_required
from apps.core.models import SiteSettings

from . import services


@login_required
@module_required('wallet')
def index(request):
    st = SiteSettings.get_solo()
    return render(request, 'wallet/index.html', {
        'balance': services.balance_of(request.user),
        'transactions': (request.user.transactions.all()[:50]),
        'payouts': st.wallet_payouts_enabled,
        'prices': [
            (_('Поднять объявление в топ на 7 дней'), st.boost_price),
            (_('Поднять анкету никах на 7 дней'), st.nikah_boost_price),
            (_('Открыть контакт в никахе'), st.nikah_chat_price),
            (_('Публикация врача'), st.doctor_publish_price),
        ],
    })


@login_required
@module_required('wallet')
def payout(request):
    if not SiteSettings.get_solo().wallet_payouts_enabled:
        messages.info(request, _('Вывод средств пока недоступен: баланс можно тратить на услуги платформы.'))
        return redirect('wallet:index')
    min_amount = SiteSettings.get_solo().min_payout
    balance = services.balance_of(request.user)
    if request.method == 'POST':
        try:
            amount = request.POST.get('amount', '').strip()
            services.create_payout_request(request.user, amount, min_amount)
            messages.success(request, _('Заявка на вывод создана — обработает админ.'))
            return redirect('wallet:index')
        except services.InsufficientFunds:
            messages.error(request, _('Недостаточно средств на балансе.'))
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, 'wallet/payout.html', {'balance': balance, 'min_amount': min_amount})
