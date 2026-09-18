"""Вход, регистрация, профиль, 2FA (TOTP) для админов."""
import base64
import io

import django_otp
import qrcode
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .audit import log_action
from .forms import LoginForm, ProfileForm, RegisterForm


def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Добро пожаловать, {user.get_display_name()}!')
        return redirect('core:home')
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    form = LoginForm(request, request.POST or None)
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
    from otp.plugins.otp_totp.models import TOTPDevice

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
