"""Пополнение баланса: выбор суммы и способа → страница оплаты провайдера."""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.core.decorators import module_required

from .models import TopUp
from .providers import PROVIDERS, ProviderNotReady, available


@login_required
@module_required('wallet')
def topup(request):
    ready = available()
    if request.method == 'POST':
        provider = PROVIDERS.get(request.POST.get('provider', ''))
        try:
            amount = Decimal(request.POST.get('amount', '0')).quantize(Decimal(1))
        except InvalidOperation:
            amount = Decimal(0)
        if not provider or provider not in ready:
            messages.error(request, 'Этот способ пока недоступен.')
        elif amount < 1000:
            messages.error(request, 'Минимальная сумма — 1 000 сум.')
        else:
            t = TopUp.objects.create(user=request.user, amount=amount, provider=provider.key)
            try:
                return redirect(provider().start(t, request))
            except ProviderNotReady as exc:
                t.status = TopUp.FAILED
                t.save(update_fields=['status'])
                messages.error(request, str(exc))
    return render(request, 'payments/topup.html', {
        'providers': list(PROVIDERS.values()), 'ready': ready,
        'amounts': [50_000, 100_000, 200_000, 500_000]})
