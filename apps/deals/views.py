"""Безопасная сделка: мои заказы, новый заказ, карточка заказа и действия."""
from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import pledge_required
from apps.wallet import services as wallet

from . import services
from .models import Order


@login_required
def index(request):
    orders = (Order.objects.filter(Q(client=request.user) | Q(provider=request.user))
              .select_related('client', 'provider'))
    return render(request, 'deals/index.html', {
        'orders': orders, 'enabled': services.settings_().escrow_enabled})


@login_required
@pledge_required
def new(request):
    st = services.settings_()
    User = get_user_model()
    to = request.GET.get('to') or request.POST.get('to')
    provider = get_object_or_404(User, pk=to, is_active=True) if (to or '').isdigit() else None
    if request.method == 'POST' and provider:
        try:
            deadline = date.fromisoformat(request.POST['deadline']) if request.POST.get('deadline') else None
            thread = None
            if (request.POST.get('thread') or '').isdigit():
                from apps.chat.models import Thread
                thread = Thread.objects.filter(pk=request.POST['thread'], participants=request.user).first()
            order = services.create(request.user, provider, request.POST.get('title', ''),
                                    request.POST.get('terms', ''), request.POST.get('amount'),
                                    deadline=deadline, kind=request.POST.get('kind', 'freelance'), thread=thread)
        except (services.DealError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, 'Заказ отправлен исполнителю. Когда он примет условия — оплатите.')
            return redirect('deals:detail', pk=order.pk)
    return render(request, 'deals/new.html', {
        'provider': provider, 'enabled': st.escrow_enabled, 'fee_percent': st.escrow_fee_percent,
        'kinds': Order.KINDS, 'thread': request.GET.get('thread', ''), 'title': request.GET.get('title', ''),
        'post': request.POST})


@login_required
def detail(request, pk):
    order = get_object_or_404(Order.objects.select_related('client', 'provider'), pk=pk)
    role = order.role_of(request.user)
    if role is None and not request.user.is_staff:
        raise Http404
    steps = [('offered', 'Предложен'), ('accepted', 'Принят'), ('funded', 'Оплачен'),
             ('delivered', 'Сдан'), ('completed', 'Выплачен')]
    order_idx = [k for k, _ in steps].index(order.status) if order.status in dict(steps) else -1
    return render(request, 'deals/detail.html', {
        'order': order, 'role': role, 'steps': steps, 'step_idx': order_idx,
        'balance': wallet.balance_of(request.user) if role == 'client' else None,
        'auto_days': services.settings_().escrow_auto_release_days,
    })


@login_required
@require_POST
def act(request, pk, action):
    order = get_object_or_404(Order, pk=pk)
    handlers = {
        'accept': lambda: services.accept(order, request.user),
        'fund': lambda: services.fund(order, request.user),
        'deliver': lambda: services.deliver(order, request.user, request.POST.get('note', '')),
        'complete': lambda: services.complete(order, request.user),
        'dispute': lambda: services.dispute(order, request.user, request.POST.get('reason', '')),
        'cancel': lambda: services.cancel(order, request.user),
    }
    if action not in handlers:
        raise Http404
    if action == 'accept' and request.POST.get('pledge') != '1':
        messages.error(request, 'Чтобы принять заказ, примите договор исполнителя.')
        return redirect('deals:detail', pk=pk)
    try:
        handlers[action]()
    except wallet.InsufficientFunds:
        messages.error(request, 'На балансе не хватает средств — пополните кошелёк.')
    except (services.DealError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, {
            'accept': 'Заказ принят. Ждём оплату от заказчика.',
            'fund': 'Оплачено. Деньги удержаны платформой до сдачи работы.',
            'deliver': 'Работа сдана. Заказчик проверит и примет.',
            'complete': 'Готово! Деньги выплачены исполнителю.',
            'dispute': 'Спор открыт. Модератор свяжется с обеими сторонами.',
            'cancel': 'Заказ отменён.',
        }[action])
    return redirect('deals:detail', pk=pk)
