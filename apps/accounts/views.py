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
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from .audit import log_action
from .forms import LoginForm, ProfileForm, RegisterForm

CAPTCHA_ERROR = _lazy('Подтвердите, что вы не робот.')


def register(request):
    from apps.core import captcha

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and not captcha.verify(request):
        form.add_error(None, CAPTCHA_ERROR)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, _('Добро пожаловать, {v1}!').format(v1=user.get_display_name()))
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
        messages.error(request, _('Слишком много попыток входа. Подождите 15 минут и попробуйте снова.'))
        return render(request, 'accounts/login.html', {'form': LoginForm(request), 'next': request.GET.get('next', '')},
                      status=429)
    from apps.core import captcha

    need_captcha = captcha.enabled() and cache.get(f'login_fail:ip:{client_ip(request)}', 0) >= 3
    form = LoginForm(request, request.POST or None)
    if request.method == 'POST' and need_captcha and not captcha.verify(request):
        form.add_error(None, CAPTCHA_ERROR)
    if request.method == 'POST' and not form.is_valid():
        for key, _limit in _login_keys(request):
            cache.add(key, 0, LOGIN_WINDOW)
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, LOGIN_WINDOW)
    if request.method == 'POST' and form.is_valid():
        cache.delete(_login_keys(request)[0][0])   # успешный вход — сброс счётчика этого логина (не IP)
        user = form.get_user()
        auth_login(request, user, backend='apps.accounts.backends.EmailBackend')
        messages.success(request, _('С возвращением, {v1}!').format(v1=user.get_display_name()))
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('core:home')
    need_captcha = captcha.enabled() and cache.get(f'login_fail:ip:{client_ip(request)}', 0) >= 3
    return render(request, 'accounts/login.html', {'form': form, 'next': request.GET.get('next', ''),
                                                   'need_captcha': need_captcha})


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
        from apps.core import captcha
        if not captcha.verify(request):
            messages.error(request, CAPTCHA_ERROR)
            return redirect('accounts:password_reset')
        key = f'pwreset:{client_ip(request)}'
        if cache.get(key, 0) >= 5:
            messages.error(request, _('Слишком много запросов. Попробуйте через час.'))
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
        messages.success(request, _('Профиль обновлён.'))
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
            messages.success(request, _('2FA подключена.'))
            return redirect('core:home')
        messages.error(request, _('Код неверный — проверьте приложение и время на телефоне.'))

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
        messages.error(request, _('Код неверный.'))
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
        'is_blocked': request.user.is_authenticated and person.blocked_by.filter(blocker=request.user).exists(),
    })


@login_required
def block_toggle(request, pk):
    """Заблокировать / разблокировать человека: не пишет вам, вы не видите друг друга в никяхе."""
    from django.contrib.auth import get_user_model
    from django.shortcuts import get_object_or_404

    from .models import UserBlock

    if request.method != 'POST':
        return redirect('accounts:blocked')
    other = get_object_or_404(get_user_model(), pk=pk)
    nxt = request.POST.get('next', '')
    nxt = nxt if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}) else ''
    if other == request.user:
        return redirect(nxt or 'accounts:profile')
    obj, created = UserBlock.objects.get_or_create(blocker=request.user, blocked=other)
    if not created:
        obj.delete()
        messages.success(request, _('{v0} разблокирован(а).').format(v0=other.get_display_name()))
    else:
        log_action(request, 'Заблокирован пользователь', f'#{other.pk}')
        messages.success(request, _('{v0} заблокирован(а): не сможет писать вам. Разблокировать — Профиль → Заблокированные.').format(v0=other.get_display_name()))
    return redirect(nxt or 'accounts:blocked')


@login_required
def blocked_list(request):
    return render(request, 'accounts/blocked.html', {
        'blocks': request.user.blocks_made.select_related('blocked')})


@login_required
def delete_account(request):
    """Удаление аккаунта (требование App Store / Google Play и закона о данных).
    Личные данные стираются, публикации снимаются, анкета никяха и фото удаляются.
    Финансовые записи (оплаты) сохраняются обезличенными — этого требует бухгалтерия."""
    from django.contrib.auth import logout

    if request.method == 'POST':
        if request.POST.get('confirm', '').strip().lower() != _('удалить'):
            messages.error(request, _('Напишите слово «удалить», чтобы подтвердить.'))
            return redirect('accounts:delete')
        user = request.user
        _wipe_user(user)
        log_action(request, 'Аккаунт удалён владельцем', f'#{user.pk}')
        logout(request)
        messages.success(request, _('Аккаунт удалён. Да вознаградит вас Аллах благом.'))
        return redirect('core:home')
    return render(request, 'accounts/delete.html')


def _wipe_user(user) -> None:
    from apps.core.models import Moderation
    from apps.core.publications import PUBLICATIONS

    profile = getattr(user, 'nikah_profile', None)
    if profile is not None:
        if profile.photo_private:
            profile.photo_private.delete(save=False)
        profile.delete()
    for pub in PUBLICATIONS:
        model = pub.get_model()
        qs = model.objects.filter(**{pub.owner: user})
        if hasattr(model, 'status'):
            qs.update(status=Moderation.REJECTED)
    if user.avatar:
        user.avatar.delete(save=False)
    user.email = f'deleted-{user.pk}@deleted.ilm4.local'
    user.username = f'deleted-{user.pk}'
    user.first_name = user.last_name = user.nickname = user.city = user.phone = ''
    user.findable_by_phone = False
    user.telegram_id = None
    user.telegram_username = ''
    user.is_active = False
    user.set_unusable_password()
    user.save()
