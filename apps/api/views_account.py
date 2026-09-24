"""API: настройки приложения, вход/регистрация, профиль, пуши, главная, уведомления, жалобы."""
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from apps.accounts import phone_verify
from apps.accounts.views import LOGIN_MAX_PER_IP, LOGIN_MAX_PER_LOGIN, LOGIN_WINDOW, client_ip

from . import tglogin
from .base import ApiError, abs_url, api, as_int, file_url, limit, module_on, page
from .models import ApiToken, PushDevice

APP_KEYS = ('prayer', 'buy', 'jobs', 'services', 'transport', 'map', 'health', 'migration', 'library', 'forum',
            'news', 'nikah', 'chat', 'wallet')


def _icon(request, key):
    from django.templatetags.static import static

    from apps.core.templatetags.icons import _icon_file
    rel = _icon_file(key)
    return abs_url(request, static(rel)) if rel else ''


@api()
def config(request):
    """Всё, что приложению нужно знать при запуске: какие разделы и функции включены.
    Выключили что-то в админке — приложение перестраивается само, без обновления."""
    from apps.core.catalog import DESCR, GROUPS
    from apps.core.models import ModuleConfig, SiteSettings
    from apps.core.templatetags.dbtr import tr
    from apps.prayer.cities import CITIES
    from apps.prayer.services import METHODS

    st = SiteSettings.get_solo()
    group_of = {k: g for g, _label, keys in GROUPS for k in keys}
    modules = []
    for m in ModuleConfig.objects.exclude(status=ModuleConfig.OFF):
        if settings.SITE_MODE == 'nikah' and m.key not in settings.NIKAH_MODE_KEYS:
            continue
        modules.append({'key': m.key, 'name': tr(m.name), 'status': m.status, 'emoji': m.icon,
                        'icon': _icon(request, m.key), 'descr': str(DESCR.get(m.key, '')),
                        'group': group_of.get(m.key, 'more'), 'native': m.key in APP_KEYS})
    return {
        'site_name': st.site_name,
        'site_url': abs_url(request, '/'),
        'min_version': st.app_min_version,
        'notice': st.app_notice,
        'languages': [{'code': c, 'name': n} for c, n in settings.LANGUAGES],
        'modules': modules,
        'groups': [{'key': g, 'name': str(label)} for g, label, _k in GROUPS],
        'features': {
            'chat': {'photo': st.chat_photos_enabled, 'video': st.chat_videos_enabled,
                     'voice': st.chat_voice_enabled, 'circle': st.chat_circles_enabled,
                     'calls': st.chat_calls_enabled, 'video_calls': st.chat_video_calls_enabled},
            'nikah': {'premium': st.nikah_premium_enabled, 'daily_limit': st.nikah_daily_limit,
                      'premium_price': st.nikah_premium_price, 'premium_days': st.nikah_premium_days,
                      'restore_price': st.nikah_restore_price, 'chat_price': st.nikah_chat_price,
                      'photo_minutes': st.nikah_photo_minutes},
            'telegram_login': bool(getattr(settings, 'TELEGRAM_BOT_USERNAME', '')
                                   and getattr(settings, 'TELEGRAM_BOT_TOKEN', '')),
            'google_login': False,
            'hadith': st.hadis_enabled,
        },
        'prayer': {
            'cities': [{'key': k, 'name': tr(v[0]), 'lat': v[1], 'lon': v[2], 'tz': v[3]} for k, v in CITIES.items()],
            'methods': [{'key': k, 'name': str(v)} for k, v in METHODS.items()],
            'default_method': 'Karachi',
        },
        'bot': getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or '',
        'map': {'maptiler': st.map_maptiler_key},
        'links': {'rules': abs_url(request, '/rules/'), 'privacy': abs_url(request, '/privacy/'),
                  'support': abs_url(request, '/support/'), 'shahada': abs_url(request, '/islam/')},
    }


# ---------- вход ----------

def me_json(request, user) -> dict:
    from apps.wallet.services import balance_of
    nk = getattr(user, 'nikah_profile', None)
    return {
        'id': user.pk, 'name': user.get_display_name(), 'nickname': user.nickname, 'first_name': user.first_name,
        'email': '' if user.email.endswith('.ilm4.local') else user.email,
        'city': user.city, 'phone': user.phone, 'language': user.language, 'avatar': file_url(request, user.avatar),
        'telegram': bool(user.telegram_id), 'verified': user.platform_verified,
        'phone_verified': user.phone_verified,
        'needs_phone': {w: phone_verify.needed(user, w) for w in ('publish', 'nikah')},
        'balance': int(balance_of(user)) if module_on('wallet') else None,
        'nikah': {'id': nk.pk, 'status': nk.status, 'active': nk.is_active, 'gender': nk.gender} if nk else None,
    }


def _issue(request, user) -> dict:
    name = str(request.data.get('device', '') or request.headers.get('User-Agent', ''))[:80]
    return {'token': ApiToken.issue(user, name), 'user': me_json(request, user)}


@api(methods=('POST',))
def login(request):
    from django.core.cache import cache

    login_value = str(request.data.get('login', '')).strip().lower()[:254]
    password = str(request.data.get('password', ''))
    keys = [(f'login_fail:u:{login_value}', LOGIN_MAX_PER_LOGIN), (f'login_fail:ip:{client_ip(request)}', LOGIN_MAX_PER_IP)]
    if any(cache.get(k, 0) >= n for k, n in keys):
        raise ApiError(_('Слишком много попыток входа. Подождите 15 минут и попробуйте снова.'), 429, 'rate')
    user = authenticate(request, username=login_value, password=password) if login_value and password else None
    if user is None:
        for k, _n in keys:
            cache.add(k, 0, LOGIN_WINDOW)
            try:
                cache.incr(k)
            except ValueError:
                cache.set(k, 1, LOGIN_WINDOW)
        raise ApiError(_('Неверный email или пароль.'), 400, 'credentials')
    cache.delete(keys[0][0])
    return _issue(request, user)


@api(methods=('POST',))
def register(request):
    from apps.accounts.forms import RegisterForm

    limit(f'api_reg:{client_ip(request)}', 5, 3600)
    pw = str(request.data.get('password', ''))
    form = RegisterForm({'email': request.data.get('email', ''), 'password1': pw, 'password2': pw,
                         'first_name': request.data.get('name', ''), 'nickname': request.data.get('name', ''),
                         'city': request.data.get('city', '')})
    if not form.is_valid():
        errors = {k: ' '.join(str(x) for x in v) for k, v in form.errors.items()}
        msg = errors.get('email') or errors.get('password2') or errors.get('password1') or next(iter(errors.values()))
        return _err(msg, errors)
    user = form.save()
    lang = str(request.data.get('language', ''))
    if lang in dict(settings.LANGUAGES):
        user.language = lang
        user.save(update_fields=['language'])
    return _issue(request, user)


def _err(msg, fields):
    from django.http import JsonResponse
    return JsonResponse({'error': msg, 'fields': fields}, status=400)


@api(methods=('POST',))
def telegram_start(request):
    limit(f'api_tg:{client_ip(request)}', 20, 3600)
    data = tglogin.create()
    if not data['url']:
        raise ApiError(_('Вход через Telegram пока не настроен.'), 400, 'tg_off')
    return data


@api(methods=('POST',))
def telegram_poll(request):
    nonce = str(request.data.get('nonce', ''))
    if not tglogin.valid_nonce(nonce):
        raise ApiError(_('Ссылка для входа устарела. Попробуйте ещё раз.'), 410, 'expired')
    user = tglogin.poll(nonce)
    if user is None:
        return {'status': 'pending'}
    return {'status': 'ok', **_issue(request, user)}


@api(methods=('POST',), auth=True)
def phone_start(request):
    """Подтверждение номера: ссылка на бота (t.me/…?start=phone_…), дальше — опрос phone_status."""
    if request.user.phone_verified:
        return {'verified': True}
    if not phone_verify.available():
        raise ApiError(_('Подтверждение номера пока не подключено.'), 400, 'tg_off')
    limit(f'api_phone:{request.user.pk}', 20, 3600)
    return {'verified': False, **phone_verify.create(request.user)}


@api(auth=True)
def phone_status(request):
    return phone_verify.status(request.user, str(request.GET.get('nonce', ''))[:40])


@api(methods=('POST',))
def password_reset(request):
    from django.contrib.auth.forms import PasswordResetForm

    limit(f'api_reset:{client_ip(request)}', 5, 3600)
    form = PasswordResetForm({'email': str(request.data.get('email', ''))})
    if form.is_valid():
        form.save(request=request, use_https=request.is_secure(),
                  email_template_name='accounts/reset_email.txt', subject_template_name='accounts/reset_subject.txt')
    return {'ok': True}   # всегда «ок» — не подсказываем, есть ли такой email


@api(methods=('POST',), auth=True)
def logout(request):
    push = str(request.data.get('push_token', ''))
    if push:
        PushDevice.objects.filter(user=request.user, token=push).delete()
    if request.api_token:
        request.api_token.delete()
    return {'ok': True}


@api(methods=('GET', 'PATCH', 'POST', 'DELETE'), auth=True)
def me(request):
    user = request.user
    if request.method in ('PATCH', 'POST'):
        d = request.data
        fields = []
        for f, n in (('nickname', 40), ('first_name', 150), ('city', 80)):
            if f in d:
                setattr(user, f, str(d[f]).strip()[:n])
                fields.append(f)
        if 'language' in d and d['language'] in dict(settings.LANGUAGES):
            user.language = d['language']
            fields.append('language')
        if 'avatar' in request.FILES:
            from apps.core.uploads import clean_image
            user.avatar = clean_image(request.FILES['avatar'])
            fields.append('avatar')
        if fields:
            user.save(update_fields=fields)
    elif request.method == 'DELETE':
        # удаление аккаунта (обязательно для App Store / Google Play)
        from apps.accounts.audit import log_action
        from apps.accounts.views import _wipe_user
        if str(request.data.get('confirm', '')).strip().lower() not in ('удалить', _('удалить').lower(), 'delete'):
            raise ApiError(_('Напишите слово «удалить», чтобы подтвердить.'))
        uid = user.pk
        _wipe_user(user)
        ApiToken.objects.filter(user_id=uid).delete()
        PushDevice.objects.filter(user_id=uid).delete()
        log_action(request, 'Аккаунт удалён владельцем (приложение)', f'#{uid}')
        return {'ok': True}
    return me_json(request, user)


@api(methods=('POST',), auth=True)
def push_register(request):
    token = str(request.data.get('token', ''))[:200]
    if not token.startswith(('ExponentPushToken[', 'ExpoPushToken[')):
        raise ApiError('token')
    PushDevice.objects.update_or_create(token=token, defaults={
        'user': request.user, 'platform': str(request.data.get('platform', ''))[:10]})
    return {'ok': True}


# ---------- главная ----------

@api()
def home(request):
    from apps.core.models import Rate, SiteSettings
    from apps.core.templatetags.dbtr import tr

    st = SiteSettings.get_solo()
    data = {
        'hadith': {'text': tr(st.hadis_text), 'source': tr(st.hadis_source), 'details': tr(st.hadis_details),
                   'image': file_url(request, st.hadis_image)} if st.hadis_enabled else None,
        'rates': [{'code': r.code, 'rate': float(r.rate)} for r in Rate.objects.all()],
        'news': [],
        'unread': 0,
    }
    if module_on('news'):
        from apps.news.models import NewsPost

        from .views_content import news_card
        data['news'] = [news_card(request, n) for n in NewsPost.objects.order_by('-is_pinned', '-created_at')[:5]]
    if request.user.is_authenticated:
        data['unread'] = request.user.notifications.filter(read=False).count()
    return data


# ---------- уведомления ----------

@api(auth=True)
def notifications(request):
    qs = request.user.notifications.all()
    return page(request, qs, lambda n: {'id': n.pk, 'text': n.text, 'url': n.url, 'read': n.read,
                                        'created_at': n.created_at.isoformat()})


@api(methods=('POST',), auth=True)
def notifications_read(request):
    ids = request.data.get('ids')
    qs = request.user.notifications.filter(read=False)
    if isinstance(ids, list):
        qs = qs.filter(pk__in=[as_int(i) for i in ids][:200])
    return {'ok': True, 'updated': qs.update(read=True)}


# ---------- кошелёк ----------

@api(auth=True, module='wallet')
def wallet(request):
    from apps.wallet.models import Transaction
    from apps.wallet.services import balance_of
    data = page(request, Transaction.objects.filter(user=request.user),
                lambda t: {'id': t.pk, 'amount': -int(t.amount) if t.is_debit else int(t.amount),
                           'kind': str(t.get_kind_display()),
                           'note': t.note, 'created_at': t.created_at.isoformat()})
    data['balance'] = int(balance_of(request.user))
    data['topup_url'] = abs_url(request, '/wallet/topup/')
    return data


# ---------- жалобы и блокировки (обязательны для магазинов приложений) ----------

REPORT_TARGETS = {'buy': 'market.listing', 'jobs': 'jobs.vacancy', 'services': 'services.service',
                  'transport': 'transport.ride', 'places': 'maps.halalplace', 'doctors': 'health.doctor',
                  'stories': 'migration.story', 'books': 'library.book', 'topics': 'forum.topic',
                  'nikah': 'nikah.nikahprofile', 'user': 'accounts.user'}


@api(methods=('POST',), auth=True)
def report(request):
    from django.contrib.contenttypes.models import ContentType
    from django.core.cache import cache

    from apps.core.models import Report
    from apps.core.my_views import REPORTS_PER_DAY, _after_report

    target = REPORT_TARGETS.get(str(request.data.get('type', '')))
    reason = str(request.data.get('reason', ''))
    if not target or reason not in dict(Report.REASONS):
        raise ApiError(_('Выберите причину жалобы.'))
    app_label, model = target.split('.')
    ct = ContentType.objects.get(app_label=app_label, model=model)
    obj = get_object_or_404(ct.model_class(), pk=as_int(request.data.get('id')))
    key = f'reports:{request.user.pk}'
    if cache.get(key, 0) >= REPORTS_PER_DAY:
        raise ApiError(_('Слишком много жалоб за сегодня. Мы уже разбираемся.'), 429)
    cache.set(key, cache.get(key, 0) + 1, 86400)
    owner = getattr(obj, 'owner', None) or getattr(obj, 'author', None) or getattr(obj, 'user', None)
    if obj == request.user or owner == request.user:
        raise ApiError(_('На себя жаловаться не нужно.'))
    _r, created = Report.objects.get_or_create(
        content_type=ct, object_id=obj.pk, reporter=request.user,
        defaults={'reason': reason, 'text': str(request.data.get('text', '')).strip()[:500]})
    if created:
        _after_report(ct, obj, reason)
    return {'ok': True, 'message': _('Спасибо! Жалоба у модератора. Мы не сообщаем автору, кто пожаловался.')}


@api(methods=('POST',), auth=True)
def block(request):
    from apps.accounts.models import UserBlock
    other = get_object_or_404(get_user_model(), pk=as_int(request.data.get('user_id')), is_active=True)
    if other == request.user:
        raise ApiError(_('Нельзя заблокировать себя'))
    if request.data.get('unblock'):
        UserBlock.objects.filter(blocker=request.user, blocked=other).delete()
        return {'ok': True, 'blocked': False}
    UserBlock.objects.get_or_create(blocker=request.user, blocked=other)
    return {'ok': True, 'blocked': True}


# ---------- переход на сайт уже со входом (оплата, подача объявления, верификация) ----------

WEB_LINK_TTL = 120


@api(methods=('POST',), auth=True)
def web_link(request):
    """Одноразовая ссылка (2 минуты): сайт откроется в браузере уже со входом.
    Нужна для того, что делается на сайте: пополнение, подача публикации."""
    import secrets

    from django.core.cache import cache
    from django.utils.http import url_has_allowed_host_and_scheme

    nxt = str(request.data.get('next', '/'))[:300]
    if not nxt.startswith('/') or not url_has_allowed_host_and_scheme(nxt, allowed_hosts=None):
        nxt = '/'
    limit(f'api_weblink:{request.user.pk}', 30, 3600)
    code = secrets.token_urlsafe(24)
    cache.set(f'weblink:{code}', {'uid': request.user.pk, 'next': nxt}, WEB_LINK_TTL)
    return {'url': abs_url(request, f'/api/v1/auth/web/{code}/')}


def web_enter(request, code):
    """Открытие одноразовой ссылки: вход в сессию сайта и переход дальше. Ссылка сгорает."""
    from django.contrib.auth import login as auth_login
    from django.core.cache import cache
    from django.shortcuts import redirect

    data = cache.get(f'weblink:{code}') if len(code) <= 40 else None
    if not data:
        return redirect('/accounts/login/')
    cache.delete(f'weblink:{code}')
    user = get_user_model().objects.filter(pk=data['uid'], is_active=True).first()
    if user is None:
        return redirect('/accounts/login/')
    if not user.is_staff:   # админам — только обычный вход с 2FA
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return redirect(data['next'])
