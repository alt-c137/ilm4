"""Никах: витрина анкет, создание своей, платное «написать» (мужчинам), буст."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import module_required, pledge_required
from apps.core.models import Moderation, SiteSettings
from apps.core.uploads import clean_image
from apps.wallet import services as wallet
from apps.wallet.models import Transaction
from apps.wallet.services import InsufficientFunds

from .models import NikahContact, NikahProfile


@module_required('nikah')
def profile_list(request):
    """Витрина анкет: просмотр бесплатный (PASSPORT §2)."""
    qs = NikahProfile.objects.filter(status=Moderation.APPROVED, is_active=True)
    gender = request.GET.get('gender', '').strip()
    city = request.GET.get('city', '').strip()
    if gender in ('M', 'F'):
        qs = qs.filter(gender=gender)
    if city:
        qs = qs.filter(city__icontains=city)
    return render(request, 'nikah/list.html', {
        'profiles': qs.select_related('user')[:60],
        'gender': gender, 'city': city,
    })


@module_required('nikah')
def profile_detail(request, pk):
    profile = get_object_or_404(NikahProfile, pk=pk, status=Moderation.APPROVED,
                                is_active=True)
    # контакт виден, если уже оплачен/бесплатен
    has_contact = False
    if request.user.is_authenticated:
        has_contact = NikahContact.objects.filter(
            from_user=request.user, to_profile=profile).exists()
    return render(request, 'nikah/detail.html', {
        'profile': profile,
        'has_contact': has_contact,
        'chat_price': SiteSettings.get_solo().nikah_chat_price,
    })


@login_required
@module_required('nikah')
@pledge_required
def profile_create(request):
    if hasattr(request.user, 'nikah_profile'):
        return redirect('nikah:mine')
    if request.method == 'POST':
        gender = request.POST.get('gender', '')
        try:
            age = int(request.POST.get('age', ''))
        except ValueError:
            age = 0
        about = request.POST.get('about', '').strip()
        errors = []
        if gender not in ('M', 'F'):
            errors.append('Укажите, кто вы.')
        if not (18 <= age <= 99):
            errors.append('Возраст — от 18 до 99.')
        if len(about) < 20:
            errors.append('Расскажите о себе хотя бы парой предложений (20+ символов).')
        try:
            photo = clean_image(request.FILES.get('photo'))
        except ValidationError as exc:
            photo = None
            errors.append(exc.messages[0] if exc.messages else 'Загрузите фото в формате JPG или PNG.')
        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            NikahProfile.objects.create(
                user=request.user, gender=gender, age=age,
                city=request.POST.get('city', '').strip()[:80],
                about=about,
                partner_expectations=request.POST.get('partner_expectations', ''),
                contact_hint=request.POST.get('contact_hint', '').strip()[:200],
                photo=photo,
            )
            messages.success(request, 'Анкета отправлена на модерацию.')
            return redirect('nikah:list')
    return render(request, 'nikah/create.html')


@login_required
@module_required('nikah')
def mine(request):
    profile = getattr(request.user, 'nikah_profile', None)
    if not profile:
        return redirect('nikah:create')
    contacts = profile.contacts_received.select_related('from_user')
    return render(request, 'nikah/mine.html', {
        'profile': profile, 'contacts': contacts,
        'boost_price': SiteSettings.get_solo().nikah_boost_price,
    })


@login_required
@module_required('nikah')
@require_POST
def open_contact(request, pk):
    """«Написать»: женщинам бесплатно, мужчинам — разовая оплата на анкету."""
    profile = get_object_or_404(NikahProfile, pk=pk, status=Moderation.APPROVED,
                                is_active=True)
    if profile.user == request.user:
        messages.error(request, 'Это ваша анкета.')
        return redirect('nikah:mine')

    contact, created = NikahContact.objects.get_or_create(
        from_user=request.user, to_profile=profile)
    # пол отправителя — из его анкеты; без анкеты считаем платным (мужская логика)
    own = getattr(request.user, 'nikah_profile', None)
    sender_is_male = own is None or own.gender == 'M'
    if created and sender_is_male and not request.user.is_superuser:
        price = SiteSettings.get_solo().nikah_chat_price
        try:
            wallet.debit(request.user, price, Transaction.PURCHASE,
                         ref=f'nikah:contact:{pk}', note=f'Контакт анкеты #{pk}')
        except InsufficientFunds:
            contact.delete()
            messages.error(request, 'Недостаточно средств — пополните кошелёк.')
            return redirect('wallet:index')
    return redirect('nikah:detail', pk=pk)


@login_required
@module_required('nikah')
@require_POST
def boost(request):
    """Поднять свою анкету в поиске на 7 дней — платно."""
    profile = getattr(request.user, 'nikah_profile', None)
    if not profile:
        return redirect('nikah:create')
    price = SiteSettings.get_solo().nikah_boost_price
    try:
        wallet.debit(request.user, price, Transaction.PURCHASE,
                     ref='nikah:boost', note='Буст анкеты никаха')
    except InsufficientFunds:
        messages.error(request, 'Недостаточно средств — пополните кошелёк.')
        return redirect('wallet:index')
    base = profile.boosted_until if profile.is_boosted else timezone.now()
    profile.boosted_until = base + timedelta(days=7)
    profile.save(update_fields=['boosted_until'])
    messages.success(request, 'Анкета поднята на 7 дней.')
    return redirect('nikah:mine')
