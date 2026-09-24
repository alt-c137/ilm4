"""ilmbuy: витрина объявлений, создание, мои объявления, буст."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.decorators import module_required, pledge_required
from apps.core.models import Moderation, SiteSettings
from apps.wallet import services as wallet
from apps.wallet.models import Transaction
from apps.wallet.services import InsufficientFunds

from .forms import ListingForm
from .models import Category, Listing


def _public_qs(request):
    qs = Listing.objects.filter(status=Moderation.APPROVED, is_active=True)

    cat = request.GET.get('cat', '').strip()
    city = request.GET.get('city', '').strip()
    q = request.GET.get('q', '').strip()
    price_min = request.GET.get('min', '').strip()
    price_max = request.GET.get('max', '').strip()
    if cat:
        qs = qs.filter(category__slug=cat)
    if city:
        qs = qs.filter(city__icontains=city)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if price_min.isdigit():
        qs = qs.filter(price__gte=price_min)
    if price_max.isdigit():
        qs = qs.filter(price__lte=price_max)
    return qs.select_related('category', 'owner')


@module_required('buy')
def listing_list(request):
    return render(request, 'market/list.html', {
        'listings': _public_qs(request)[:60],
        'categories': Category.objects.all(),
        'cat': request.GET.get('cat', ''),
        'city': request.GET.get('city', ''),
        'q': request.GET.get('q', ''),
    })


@module_required('buy')
def listing_detail(request, pk):
    listing = get_object_or_404(Listing, pk=pk, status=Moderation.APPROVED, is_active=True)
    Listing.objects.filter(pk=pk).update(views=F('views') + 1)
    return render(request, 'market/detail.html', {'listing': listing})


@login_required
@module_required('buy')
@pledge_required
def listing_create(request):
    form = ListingForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        listing = form.save(commit=False)
        listing.owner = request.user
        # без модерации (настройка админа) публикуем сразу
        if not SiteSettings.get_solo().market_moderation:
            listing.status = Moderation.APPROVED
        listing.save()
        form.save_m2m()  # теги
        messages.success(
            request,
            _('Опубликовано!') if listing.is_approved else _('Отправлено на модерацию.'))
        return redirect('market:my')
    return render(request, 'market/form.html', {'form': form, 'categories': Category.objects.all()})


@login_required
@module_required('buy')
def my_listings(request):
    return render(request, 'market/my.html', {
        'listings': request.user.listings.all(),
        'boost_price': SiteSettings.get_solo().boost_price,
    })


@login_required
@module_required('buy')
@require_POST
def listing_boost(request, pk):
    """Поднять объявление в поиске на 7 дней — платное действие (кошелёк)."""
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)
    price = SiteSettings.get_solo().boost_price
    try:
        wallet.debit(request.user, price, Transaction.PURCHASE,
                     ref=f'market:boost:{pk}', note=f'Буст объявления #{pk}')
    except InsufficientFunds:
        messages.error(request, _('Недостаточно средств — пополните кошелёк.'))
        return redirect('wallet:index')
    base = listing.boosted_until if listing.is_boosted else timezone.now()
    listing.boosted_until = base + timedelta(days=7)
    listing.save(update_fields=['boosted_until'])
    messages.success(request, _('Объявление поднято на 7 дней.'))
    return redirect('market:my')
