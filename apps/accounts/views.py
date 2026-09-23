"""Вход, регистрация, профиль, 2FA (TOTP) для админов."""
import base64
import io

import django_otp
import qrcode
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .audit import log_action
from .forms import LoginForm, ProfileForm, RegisterForm


def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Добро пожаловать, {user.get_display_name()}!')
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('core:home')
    return render(request, 'accounts/register.html', {'form': form, 'next': request.GET.get('next', '')})


# Защита от подбора пароля: не больше N неудачных попыток за окно — по логину и по IP
LOGIN_WINDOW = 15 * 60
LOGIN_MAX_PER_LOGIN = 8
LOGIN_MAX_PER_IP = 30


def client_ip(request) -> str:
    """IP посетителя: nginx кладёт его в X-Real-IP (за Cloudflare — из CF-Connecting-IP)."""
    return (request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR') or '').strip()


def _login_keys(request):
    login_value = (request.POST.get('login') or '').strip().lower()[:254]
    return [(f'login_fail:u:{login_value}', LOGIN_MAX_PER_LOGIN),
            (f'login_fail:ip:{client_ip(request)}', LOGIN_MAX_PER_IP)]


def login_view(request):
    from django.core.cache import cache

    if request.method == 'POST' and any(cache.get(k, 0) >= limit for k, limit in _login_keys(request)):
        messages.error(request, 'Слишком много попыток входа. Подождите 15 минут и попробуйте снова.')
        return render(request, 'accounts/login.html', {'form': LoginForm(request), 'next': request.GET.get('next', '')},
                      status=429)
    form = LoginForm(request, request.POST or None)
    if request.method == 'POST' and not form.is_valid():
        for key, _limit in _login_keys(request):
            cache.add(key, 0, LOGIN_WINDOW)
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, LOGIN_WINDOW)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        auth_login(request, user, backend='apps.accounts.backends.EmailBackend')
        messages.success(request, f'С возвращением, {user.get_display_name()}!')
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('core:home')
    return render(request, 'accounts/login.html', {'form': form, 'next': request.GET.get('next', '')})


# Выход — только POST (Django 5), кнопка-форма в шапке
logout_view = LogoutView.as_view()


# --- Восстановление пароля по email (стандартные токены Django: одноразовые, 3 дня) ---
_reset_view = auth_views.PasswordResetView.as_view(
    template_name='accounts/reset_form.html',
    email_template_name='accounts/reset_email.txt',
    subject_template_name='accounts/reset_subject.txt',
    success_url=reverse_lazy('accounts:password_reset_done'),
)


def password_reset(request):
    """Не больше 5 писем в час с одного IP — чтобы форму не использовали для спама."""
    from django.core.cache import cache

    if request.method == 'POST':
        key = f'pwreset:{client_ip(request)}'
        if cache.get(key, 0) >= 5:
            messages.error(request, 'Слишком много запросов. Попробуйте через час.')
            return redirect('accounts:password_reset')
        cache.set(key, cache.get(key, 0) + 1, 3600)
    return _reset_view(request)


password_reset_done = auth_views.PasswordResetDoneView.as_view(template_name='accounts/reset_done.html')
password_reset_confirm = auth_views.PasswordResetConfirmView.as_view(
    template_name='accounts/reset_confirm.html',
    success_url=reverse_lazy('accounts:password_reset_complete'),
)
password_reset_complete = auth_views.PasswordResetCompleteView.as_view(
    template_name='accounts/reset_complete.html')


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Профиль обновлён.')
        return redirect('accounts:profile')
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def two_factor_setup(request):
    """Подключение TOTP: QR + подтверждение кодом. Обязательно для staff."""
    from django_otp.plugins.otp_totp.models import TOTPDevice

    device = (request.user.totpdevice_set.filter(confirmed=False).first()
              or TOTPDevice.objects.create(user=request.user, name='Основной', confirmed=False))
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        if device.verify_token(code):
            device.confirmed = True
            device.save()
            django_otp.login(request, device)
            log_action(request, 'Подключена 2FA', request.user.email)
            messages.success(request, '2FA подключена.')
            return redirect('core:home')
        messages.error(request, 'Код неверный — проверьте приложение и время на телефоне.')

    # QR данными (data-URI), без внешних сервисов
    img = qrcode.make(device.config_url)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_data = base64.b64encode(buffer.getvalue()).decode()
    return render(request, 'accounts/2fa_setup.html', {'qr_data': qr_data})


@login_required
def two_factor_verify(request):
    """Ввод кода при входе (для staff с уже подключённой 2FA)."""
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        for device in request.user.totpdevice_set.filter(confirmed=True):
            if device.verify_token(code):
                django_otp.login(request, device)
                return redirect('core:home')
        messages.error(request, 'Код неверный.')
    return render(request, 'accounts/2fa_verify.html')


def public_profile(request, pk):
    """Публичная страница участника: продавец / исполнитель / перевозчик.
    Репутация — у человека, а не у одного объявления: рейтинг и отзывы здесь."""
    from django.contrib.auth import get_user_model
    from django.shortcuts import get_object_or_404

    from apps.core.models import Moderation

    person = get_object_or_404(get_user_model(), pk=pk, is_active=True)
    approved = {'status': Moderation.APPROVED}
    return render(request, 'accounts/public.html', {
        'person': person,
        'listings': person.listings.filter(is_active=True, **approved)[:8],
        'rides': person.rides.filter(**approved)[:6],
        'services': person.services.filter(**approved)[:6],
        'vacancies': person.vacancies.filter(**approved)[:6],
    })
