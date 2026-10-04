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
from django.urls import reverse, reverse_lazy
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
    return render(request, 'accounts/register.html', {'form': form, 'next': request.GET.get('next', ''),
                                                      'tg_link': _tg_link()})


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
        response = redirect(next_url if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})
                            else 'core:home')
        from . import multi
        pairs = multi.read(request)
        if pairs:                                             # «Добавить аккаунт»: новый вход встаёт рядом с запомненными
            multi.write(response, multi.remember(user, pairs), request.is_secure())
        return response
    need_captcha = captcha.enabled() and cache.get(f'login_fail:ip:{client_ip(request)}', 0) >= 3
    from . import multi
    return render(request, 'accounts/login.html', {'form': form, 'next': request.GET.get('next', ''),
                                                   'need_captcha': need_captcha, 'tg_link': _tg_link(),
                                                   'remembered': [r for r in multi.accounts(request) if r['ok']]})


# Выход — только POST (Django 5), кнопка-форма в шапке. Если на устройстве есть другие аккаунты — открывается следующий.
_logout = LogoutView.as_view()


def logout_view(request):
    from . import multi
    if request.method != 'POST' or not request.user.is_authenticated:
        return _logout(request)
    pairs = multi.forget(request.user.pk, multi.read(request))
    nxt = next((multi.resolve(pairs, u) for u, _t in pairs), None)
    response = _logout(request)
    if nxt is not None:
        auth_login(request, nxt, backend='django.contrib.auth.backends.ModelBackend')
        response = redirect('core:home')
    multi.write(response, pairs, request.is_secure())
    return response


def accounts_switch(request):
    """Переключиться на запомненный аккаунт (и со страницы входа — «вернуться в аккаунт»). Доказательство — ключ в куке."""
    from . import multi
    if request.method != 'POST':
        return redirect('accounts:accounts')
    pairs = multi.read(request)
    uid = int(request.POST.get('user') or 0)
    user = multi.resolve(pairs, uid)
    if user is None:
        messages.error(request, _('Этот вход устарел — войдите в аккаунт заново.'))
        pairs = multi.forget(uid, pairs)
        response = redirect('accounts:login')
    else:
        if request.user.is_authenticated:
            pairs = multi.remember(request.user, pairs)       # текущий тоже остаётся на устройстве
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        response = redirect('core:home')
    multi.write(response, pairs, request.is_secure())
    return response


@login_required
def personas_view(request):
    """«Мои профили» — маски: как человека видят в объявлениях и в сообществах (по одной на раздел), плюс анкета никяха."""
    from apps.core.models import ModuleConfig

    from . import people
    if request.method == 'POST':
        section = request.POST.get('section', '')
        try:
            if request.POST.get('remove'):
                people.delete_persona(request.user, section)
            else:
                people.save_persona(request.user, section, request.POST.get('name', ''),
                                    link_main=section != people.BOARD or request.POST.get('link_main') == '1',
                                    avatar=request.FILES.get('avatar'))
            messages.success(request, _('Сохранено.'))
        except people.PeopleError as exc:
            messages.error(request, exc.message)
        return redirect('accounts:personas')
    mine = people.personas(request.user)
    sections = [
        {'key': people.BOARD, 'title': _('Объявления, работа, услуги'), 'p': mine[people.BOARD],
         'hint': _('Под этим именем вас видят в объявлениях, вакансиях и в чатах по ним.')},
        {'key': people.SPACES, 'title': _('Сообщества'), 'p': mine[people.SPACES],
         'hint': _('Ваше имя во всех сообществах. В отдельном сообществе можно поставить свой ник — он важнее.')},
    ]
    return render(request, 'accounts/personas.html', {
        'sections': sections, 'nikah': getattr(request.user, 'nikah_profile', None),
        'nikah_on': ModuleConfig.objects.filter(key='nikah', status=ModuleConfig.ON).exists()})


@login_required
def accounts_view(request):
    """«Аккаунты» — как в Telegram: кто вошёл на этом устройстве, переключиться, добавить ещё один (до трёх), убрать."""
    from django.contrib.auth import logout

    from . import multi
    pairs = multi.read(request)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            if len({u for u, _t in pairs} | {request.user.pk}) >= multi.MAX:
                messages.error(request, _('На одном устройстве — не больше трёх аккаунтов.'))
                return redirect('accounts:accounts')
            pairs = multi.remember(request.user, pairs)
            logout(request)                                   # сессию освобождаем: дальше — вход во второй аккаунт
            response = redirect(reverse('accounts:login') + '?add=1')
            multi.write(response, pairs, request.is_secure())
            return response
        if action == 'forget':
            pairs = multi.forget(int(request.POST.get('user') or 0), pairs)
            response = redirect('accounts:accounts')
            multi.write(response, pairs, request.is_secure())
            return response
    rows = multi.accounts(request)
    if not any(r['current'] for r in rows):
        rows.insert(0, {'user': request.user, 'current': True, 'ok': True})
    return render(request, 'accounts/accounts.html', {'rows': rows, 'can_add': len(rows) < multi.MAX, 'max': multi.MAX})


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
    from . import people
    from .models import SocialLink
    user = request.user
    form = ProfileForm(request.POST or None, request.FILES or None, instance=user)
    link_error = ''
    if request.method == 'POST' and form.is_valid():
        rows = [{'kind': k, 'value': v, 'privacy': pr} for k, v, pr in zip(
            request.POST.getlist('link_kind'), request.POST.getlist('link_value'), request.POST.getlist('link_privacy'))]
        try:
            people.set_links(user, rows)
        except people.PeopleError as exc:
            link_error = exc.message
        people.set_links_view(user, request.POST.get('links_view', ''))
        form.save()
        from apps.social import services as social
        social.set_private(user, user.is_private)          # открыл профиль — ждавшие заявки становятся подписками
        if not link_error:
            messages.success(request, _('Сохранено.'))
            sec = request.POST.get('s', '')
            return redirect(reverse('accounts:profile') + (f'?s={sec}' if sec in ('edit', 'privacy', 'links') else ''))
    from django.contrib.auth import get_user_model
    User = get_user_model()
    me = User.objects.get(pk=user.pk)                 # без несохранённых правок формы
    return render(request, 'accounts/profile.html', {
        'photos': _photo_rows(me),
        'form': form, 'me': me, 'links': (my_links := people.links_for(me, me)), 'link_error': link_error,
        'links_view': people.links_view(me, len(my_links)), 'links_mode': (me.ui or {}).get('links_view', 'auto'),
        'link_kinds': SocialLink.KINDS, 'privacy_levels': User.PRIVACY,
        'close_friends': people.close_friends(user)[:50],
        'section': _profile_section(request)})


def _profile_section(request) -> str:
    """Какой раздел настроек показать: Мой аккаунт (edit) / Конфиденциальность / Ссылки. Пусто — сам профиль."""
    sec = request.POST.get('s') or request.GET.get('s') or ('edit' if request.GET.get('edit') == '1' else '')
    if request.method == 'POST' and not sec:
        sec = 'edit'                                           # форма не прошла проверку — показываем её с ошибками
    return sec if sec in ('edit', 'privacy', 'links') else ''


def _photo_rows(person) -> list:
    """Фото профиля для просмотра на весь экран (главное — первым)."""
    from django.utils.formats import date_format

    from . import people
    return [{'id': ph.pk, 'url': ph.image.url, 'date': date_format(ph.created_at, 'j E Y'),
             'name': person.get_display_name()} for ph in people.photos(person)]


@login_required
def photos(request):
    """Мои фото профиля: сделать главным / удалить (кнопки в просмотре фото)."""
    from django.http import JsonResponse

    from . import people
    if request.method != 'POST':
        return JsonResponse({'items': _photo_rows(request.user)})
    try:
        if request.POST.get('main'):
            people.set_main_photo(request.user, request.POST.get('main'))
        elif request.POST.get('delete'):
            people.delete_photo(request.user, request.POST.get('delete'))
    except (people.PeopleError, ValueError) as exc:
        return JsonResponse({'error': getattr(exc, 'message', str(exc))}, status=400)
    request.user.refresh_from_db()
    return JsonResponse({'items': _photo_rows(request.user)})


@login_required
def two_factor_setup(request):
    """Двухшаговая защита: QR для приложения-аутентификатора + подтверждение кодом. Админам обязательна, остальным — по желанию."""
    from django_otp.plugins.otp_totp.models import TOTPDevice

    from . import twofa
    if twofa.enabled(request.user):                       # уже подключена — страница управления
        if request.method == 'POST' and request.POST.get('action') == 'disable':
            if request.user.is_staff:
                messages.error(request, _('Сотрудникам двухшаговая защита обязательна.'))
            elif twofa.check(request.user, request.POST.get('code', '')):
                twofa.disable(request.user)
                log_action(request, 'Отключена 2FA', request.user.email)
                messages.success(request, _('Двухшаговая защита отключена.'))
                return redirect('core:settings')
            else:
                messages.error(request, _('Код неверный — проверьте приложение и время на телефоне.'))
        return render(request, 'accounts/2fa_setup.html', {'on': True})
    device = (request.user.totpdevice_set.filter(confirmed=False).first()
              or TOTPDevice.objects.create(user=request.user, name='Основной', confirmed=False))
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        if device.verify_token(code):
            device.confirmed = True
            device.save()
            twofa.forget(request.user)
            django_otp.login(request, device)
            log_action(request, 'Подключена 2FA', request.user.email)
            messages.success(request, _('Двухшаговая защита подключена.'))
            return redirect('core:settings')
        messages.error(request, _('Код неверный — проверьте приложение и время на телефоне.'))

    # QR данными (data-URI), без внешних сервисов
    img = qrcode.make(device.config_url)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_data = base64.b64encode(buffer.getvalue()).decode()
    import base64 as _b64
    secret = _b64.b32encode(device.bin_key).decode().rstrip('=')          # для ручного ввода, если камера не читает QR
    return render(request, 'accounts/2fa_setup.html', {'qr_data': qr_data, 'secret': ' '.join(secret[k:k + 4] for k in range(0, len(secret), 4))})


@login_required
def two_factor_verify(request):
    """Ввод кода после входа — для всех, у кого подключена двухшаговая защита."""
    from . import twofa
    if request.user.is_verified():
        return redirect('core:home')
    if request.method == 'POST':
        device = twofa.check(request.user, request.POST.get('code', ''))
        if device is not None:
            django_otp.login(request, device)
            nxt = request.POST.get('next') or ''
            return redirect(nxt if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}) else 'core:home')
        messages.error(request, _('Слишком много неверных кодов. Подождите 15 минут.') if twofa.blocked(request.user) else _('Код неверный.'))
    return render(request, 'accounts/2fa_verify.html', {'next': request.GET.get('next', '')})


def _call_flags(thread) -> dict:
    """Включены ли звонки (кнопки «Звонок» и «Видео» в профиле человека)."""
    from apps.api.base import module_on
    if not module_on('chat'):
        return {}
    from apps.chat import services as chat
    f = chat.flags(thread)
    return {'calls': f.get('calls'), 'video_calls': f.get('video_calls')}


def public_profile(request, pk):
    """Публичная страница участника: продавец / исполнитель / перевозчик.
    Репутация — у человека, а не у одного объявления: рейтинг и отзывы здесь."""
    from django.contrib.auth import get_user_model
    from django.shortcuts import get_object_or_404

    from apps.core.models import Moderation

    from . import people
    person = get_object_or_404(get_user_model(), pk=pk, is_active=True)
    approved = {'status': Moderation.APPROVED}
    viewer = request.user if request.user.is_authenticated else None
    mine = viewer is not None and viewer.pk == person.pk
    close = people.is_close(person, viewer)                    # зритель в близких у хозяина страницы
    presence = people.presence(person, viewer, close)
    thread, shared = None, {}
    if viewer is not None and not mine:
        from apps.chat import services as chat
        thread = chat.direct_between(viewer, person)
        if thread is not None:
            shared = {'media': chat.shared_media(thread, viewer, 'media', limit=30),
                      'files': chat.shared_media(thread, viewer, 'files', limit=30),
                      'muted': chat.is_muted(thread, viewer)}
    from apps.social import services as social
    wall, follow = [], {}
    if social.module_on('feed'):
        wall = [social.post_item(p, viewer) for p in social.wall(person, viewer, limit=20)]
        social.decorate(wall, viewer)
        follow = {'on': social.is_following(viewer, person), 'state': social.follow_state(viewer, person),
                  'locked': not social.can_see_wall(person, viewer), **social.counts(person, viewer)}
    return render(request, 'accounts/public.html', {
        'wall': wall, 'follow': follow,
        'gifts': social.gifts_of(person) if social.module_on('gifts') else [],
        'photos': _photo_rows(person),
        'person': person, 'mine': mine,
        'status': people.status_text(presence), 'online': presence['online'],
        'phone': people.phone_for(person, viewer, close), 'links': (shown_links := people.links_for(person, viewer, close)),
        'links_view': people.links_view(person, len(shown_links)),
        'is_close': viewer is not None and not mine and people.is_close(viewer, person),
        'is_contact': viewer is not None and not mine and people.is_contact(viewer, person),
        'thread': thread, 'shared': shared,
        'calls': _call_flags(thread) if viewer is not None and not mine else {},
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
def close_toggle(request, pk):
    """Добавить человека в близкие друзья / убрать: им видно то, что скрыто от остальных."""
    from django.contrib.auth import get_user_model
    from django.shortcuts import get_object_or_404

    from . import people
    other = get_object_or_404(get_user_model(), pk=pk, is_active=True)
    if request.method == 'POST' and other.pk != request.user.pk:
        on = people.set_close(request.user, other, not people.is_close(request.user, other))
        name = other.get_display_name()
        messages.success(request, _('{v0} — в близких друзьях.').format(v0=name) if on
                         else _('{v0} убран(а) из близких друзей.').format(v0=name))
    nxt = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = ''
    return redirect(nxt or reverse('accounts:public', args=[pk]))


def ping(request):
    """Открытая вкладка раз в минуту сообщает «я в сети» (сама отметка — в LastSeenMiddleware)."""
    from django.http import JsonResponse
    if request.user.is_authenticated:
        from . import devices
        devices.touch(request)                      # «Устройства»: когда этим сеансом пользовались последний раз
    return JsonResponse({'ok': True})


# ---------- устройства: активные сеансы и вход по QR-коду (apps/accounts/devices.py) ----------

@login_required
def devices_view(request):
    """«Устройства» — как «Активные сеансы» в Telegram: где открыт аккаунт, завершить один сеанс или все остальные."""
    from . import devices, twofa
    key = request.session.session_key or ''
    if request.method == 'POST':
        if request.POST.get('others'):
            n = devices.terminate_others(request.user, key)
            messages.success(request, _('Завершено сеансов: {n}.').format(n=n))
        elif request.POST.get('kind') in ('web', 'app') and (request.POST.get('id') or '').isdigit():
            devices.terminate(request.user, request.POST['kind'], int(request.POST['id']))
            messages.success(request, _('Сеанс завершён.'))
        return redirect('accounts:devices')
    devices.touch(request)
    rows = devices.sessions(request.user, key)
    return render(request, 'accounts/devices.html', {'rows': rows, 'others': sum(1 for r in rows if not r['current']),
                                                     'twofa': twofa.enabled(request.user)})


def qr_start(request):
    """Страница входа просит QR-код: одноразовый, на 3 минуты, привязан к этому браузеру."""
    from django.core.cache import cache
    from django.http import JsonResponse

    from . import devices
    if request.method != 'POST' or request.user.is_authenticated:
        return JsonResponse({'error': 'bad'}, status=400)
    key = f'qr_new:{client_ip(request)}'
    if cache.get(key, 0) >= 40:
        return JsonResponse({'error': _('Слишком часто. Попробуйте через несколько минут.')}, status=429)
    cache.set(key, cache.get(key, 0) + 1, 600)
    token = devices.qr_new(request)
    url = request.build_absolute_uri(reverse('accounts:qr_confirm', args=[token]))
    return JsonResponse({'img': devices.qr_image(url), 'ttl': devices.QR_TTL})


def qr_status(request):
    """Компьютер ждёт подтверждения с телефона. Подтвердили — входим (двухшаговую защиту это не обходит)."""
    from django.http import JsonResponse

    from . import devices
    state, user = devices.qr_take(request)
    if state != 'ok':
        return JsonResponse({'state': state})
    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    nxt = request.GET.get('next') or ''
    return JsonResponse({'state': 'ok', 'next': nxt if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}) else '/'})


@login_required
def qr_confirm(request, token):
    """Телефон отсканировал код: показать, какое устройство просит вход, и спросить подтверждение."""
    from . import devices
    info = devices.qr_info(token)
    done = False
    if request.method == 'POST' and info is not None:
        if request.POST.get('ok') == '1' and devices.qr_approve(token, request.user):
            log_action(request, 'Вход по QR подтверждён', f"{info.get('ua', '')} {info.get('ip', '')}")
            done = True
        else:
            return redirect('core:home')
    return render(request, 'accounts/qr_confirm.html', {'info': info, 'done': done, 'token': token})


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
    for photo in user.photos.all():           # вся история фото профиля
        photo.image.delete(save=False)
        photo.delete()
    if user.avatar:
        user.avatar.delete(save=False)
    user.email = f'deleted-{user.pk}@deleted.ilm4.local'
    user.username = f'deleted-{user.pk}'
    user.first_name = user.last_name = user.nickname = user.city = user.phone = user.bio = ''
    user.handle = None                       # имя освобождается
    user.last_seen_at = None
    user.social_links.all().delete()
    user.close_friends.all().delete()
    user.close_of.all().delete()
    user.findable_by_phone = False
    user.phone_verified_at = None
    user.telegram_id = None
    user.telegram_username = ''
    user.is_active = False
    user.set_unusable_password()
    user.save()


# ---------- подтверждение номера через Telegram (apps/accounts/phone_verify.py) ----------

def _safe(request, url: str, default: str = '/') -> str:
    return url if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}) else default


@login_required
def phone(request):
    from . import phone_verify
    next_url = _safe(request, request.GET.get('next', ''), reverse_lazy('accounts:profile'))
    if request.user.phone_verified:
        if request.GET.get('next'):
            return redirect(next_url)
        return render(request, 'accounts/phone.html', {'done': True, 'masked': phone_verify.mask(request.user.phone)})
    if not phone_verify.available():
        messages.info(request, _('Подтверждение номера пока не подключено.'))
        return redirect(next_url)
    link = phone_verify.create(request.user)
    return render(request, 'accounts/phone.html', {'link': link, 'next': next_url,
                                                   'why': request.GET.get('why', '')})


@login_required
def phone_status(request):
    from django.http import JsonResponse

    from . import phone_verify
    return JsonResponse(phone_verify.status(request.user, request.GET.get('nonce', '')[:40]))



# ---------- вход через Telegram-бота на сайте (тот же механизм, что в приложении: apps/api/tglogin.py) ----------

def _tg_link():
    from apps.api import tglogin

    from . import phone_verify
    return tglogin.create() if phone_verify.available() else None


def tg_poll(request):
    """Страница входа спрашивает раз в 2 секунды: вход в боте подтверждён? — входим."""
    from django.http import JsonResponse

    from apps.api import tglogin
    nonce = (request.POST.get('nonce') or '')[:40]
    if request.method != 'POST' or not tglogin.valid_nonce(nonce):
        return JsonResponse({'status': 'expired'}, status=410)
    user = tglogin.poll(nonce)
    if user is None:
        return JsonResponse({'status': 'pending'})
    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    log_action(request, 'Вход через Telegram-бота (сайт)', f'user#{user.pk}')
    messages.success(request, _('С возвращением, {v1}!').format(v1=user.get_display_name()))
    return JsonResponse({'status': 'ok', 'next': _safe(request, request.POST.get('next', ''), '/')})
