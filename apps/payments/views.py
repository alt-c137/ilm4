"""Пополнение баланса: сумма и способ → страница оплаты провайдера (или счёт Stars в Telegram)."""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import module_required

from .models import TopUp
from .providers import PROVIDERS, ProviderNotReady, Stars, available

MIN_AMOUNT = 1000
MAX_AMOUNT = 50_000_000


def _safe_next(url: str) -> str:
    return url if url.startswith('/') and not url.startswith('//') else ''


@login_required
@module_required('wallet')
def topup(request):
    ready = available()
    wants_json = 'application/json' in request.headers.get('Accept', '')
    nxt = _safe_next(request.POST.get('next') or request.GET.get('next', ''))
    if request.method == 'POST':
        provider = PROVIDERS.get(request.POST.get('provider', ''))
        raw = request.POST.get('custom') or request.POST.get('amount', '0')
        try:
            amount = Decimal(str(raw).replace(' ', '')).quantize(Decimal(1))
        except InvalidOperation:
            amount = Decimal(0)
        error = ''
        if not provider or provider not in ready:
            error = 'Этот способ пока недоступен.'
        elif not MIN_AMOUNT <= amount <= MAX_AMOUNT:
            error = f'Сумма — от {MIN_AMOUNT:,} сум.'.replace(',', ' ')
        elif provider is Stars and not request.user.telegram_id:
            error = 'Оплата звёздами — из Telegram: откройте ilm4 через бота.'
        if not error:
            t = TopUp.objects.create(user=request.user, amount=amount, provider=provider.key)
            try:
                url = provider().start(t, request)
            except ProviderNotReady as exc:
                t.status = TopUp.FAILED
                t.save(update_fields=['status'])
                error = str(exc)
            else:
                if nxt:
                    request.session['topup_next'] = nxt
                if wants_json:
                    return JsonResponse({'ok': True, 'url': url, 'stars': provider is Stars,
                                         'done': f'/payments/done/{t.pk}/'})
                return redirect(url)
        if wants_json:
            return JsonResponse({'ok': False, 'error': error}, status=400)
        messages.error(request, error)
    return render(request, 'payments/topup.html', {
        'providers': list(PROVIDERS.values()), 'ready': ready, 'next': nxt,
        'amounts': [50_000, 100_000, 200_000, 500_000, 1_000_000]})


@login_required
def done(request, pk):
    t = get_object_or_404(TopUp, pk=pk, user=request.user)
    if request.headers.get('Accept', '').startswith('application/json'):
        return JsonResponse({'status': t.status})
    return render(request, 'payments/done.html', {'t': t, 'next': request.session.get('topup_next', '')})
