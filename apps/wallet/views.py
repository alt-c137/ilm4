"""Кошелёк пользователя: баланс, история, заявка на вывод."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.core.models import SiteSettings

from . import services
from .models import Transaction


@login_required
def index(request):
    return render(request, 'wallet/index.html', {
        'balance': services.balance_of(request.user),
        'transactions': (request.user.transactions.all()[:50]),
    })


@login_required
def payout(request):
    min_amount = SiteSettings.get_solo().min_payout
    balance = services.balance_of(request.user)
    if request.method == 'POST':
        try:
            amount = request.POST.get('amount', '').strip()
            services.create_payout_request(request.user, amount, min_amount)
            messages.success(request, 'Заявка на вывод создана — обработает админ.')
            return redirect('wallet:index')
        except services.InsufficientFunds:
            messages.error(request, 'Недостаточно средств на балансе.')
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, 'wallet/payout.html', {'balance': balance, 'min_amount': min_amount})
