"""Устройства: активные сеансы (сайт и приложение) и вход по QR-коду — как в Telegram.

Сеансы. Вход на сайт создаёт сессию Django; сигнал входа записывает DeviceSession (браузер, IP, время). Человек видит
список и может завершить любой сеанс или все, кроме текущего. Входы приложения — строки api.ApiToken.

Вход по QR. На странице входа компьютер показывает код; человек сканирует его телефоном, на котором уже вошёл
(приложением или камерой — откроется сайт), видит, что за устройство просит вход, и подтверждает. Код живёт 3 минуты,
срабатывает один раз и привязан к тому браузеру, который его показал. Двухшаговую защиту QR не обходит — код
из аутентификатора новое устройство спросит всё равно.
"""
import base64
import io
import secrets

from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.utils import timezone

QR_TTL = 180
TOUCH_EVERY = 300


# ---------- что за устройство ----------

def describe(ua: str) -> str:
    """«Chrome · Windows» из строки User-Agent (без точности до версии — человеку нужна только узнаваемость)."""
    ua = ua or ''
    low = ua.lower()
    if 'ilm4-app' in low or 'expo' in low or 'okhttp' in low:
        return 'ilm4 · ' + ('iPhone' if 'iphone' in low or 'ios' in low or 'darwin' in low else 'Android' if 'android' in low or 'okhttp' in low else 'приложение')
    browser = next((name for key, name in (('edg/', 'Edge'), ('opr/', 'Opera'), ('yabrowser', 'Яндекс Браузер'), ('firefox', 'Firefox'),
                                           ('chrome', 'Chrome'), ('safari', 'Safari')) if key in low), 'Браузер')
    system = next((name for key, name in (('android', 'Android'), ('iphone', 'iPhone'), ('ipad', 'iPad'), ('windows', 'Windows'),
                                          ('mac os', 'macOS'), ('linux', 'Linux')) if key in low), '')
    return f'{browser} · {system}' if system else browser


def _ip(request) -> str:
    from .views import client_ip
    return client_ip(request)[:45] or None


# ---------- сеансы ----------

def record(request, user) -> None:
    """Запомнить сеанс сайта (зовётся сигналом входа)."""
    from .models import DeviceSession
    key = request.session.session_key
    if not key:
        return
    DeviceSession.objects.update_or_create(session_key=key, defaults={
        'user': user, 'ua': (request.META.get('HTTP_USER_AGENT') or '')[:300], 'ip': _ip(request), 'last_seen_at': timezone.now()})


def touch(request) -> None:
    """Отметить, что сеансом пользуются (не чаще раза в 5 минут). Сеанс, вошедший до появления списка, — дозаписать."""
    from .models import DeviceSession
    key = request.session.session_key
    if not key or cache.get(f'devsess:{key}'):
        return
    cache.set(f'devsess:{key}', 1, TOUCH_EVERY)
    if not DeviceSession.objects.filter(session_key=key).update(last_seen_at=timezone.now()):
        record(request, request.user)


def forget(session_key: str) -> None:
    from .models import DeviceSession
    DeviceSession.objects.filter(session_key=session_key).delete()


def sessions(user, current_key: str = '', current_token=None) -> list:
    """Все входы человека: сайт и приложение. Текущий — первым. Сеансы, которых уже нет в Django, убираются."""
    from apps.api.models import ApiToken

    from .models import DeviceSession
    rows = list(DeviceSession.objects.filter(user=user))
    alive = set(Session.objects.filter(session_key__in=[r.session_key for r in rows], expire_date__gt=timezone.now())
                .values_list('session_key', flat=True))
    out = []
    for r in rows:
        if r.session_key not in alive:
            r.delete()
            continue
        out.append({'kind': 'web', 'id': r.pk, 'title': describe(r.ua), 'ip': r.ip or '', 'last': r.last_seen_at,
                    'created': r.created_at, 'current': r.session_key == current_key})
    for t in ApiToken.objects.filter(user=user):
        out.append({'kind': 'app', 'id': t.pk, 'title': describe('ilm4-app ' + t.name), 'ip': '', 'last': t.last_used_at or t.created_at,
                    'created': t.created_at, 'current': current_token is not None and t.pk == current_token.pk})
    out.sort(key=lambda x: (not x['current'], -x['last'].timestamp()))
    return out


def terminate(user, kind: str, pk) -> bool:
    """Завершить один сеанс: этот браузер или телефон больше не в аккаунте."""
    from apps.api.models import ApiToken

    from .models import DeviceSession
    if kind == 'app':
        return bool(ApiToken.objects.filter(user=user, pk=pk).delete()[0])
    row = DeviceSession.objects.filter(user=user, pk=pk).first()
    if row is None:
        return False
    Session.objects.filter(session_key=row.session_key).delete()
    row.delete()
    return True


def terminate_others(user, current_key: str = '', current_token=None) -> int:
    """Завершить все сеансы, кроме текущего (как «Завершить все другие сеансы» в Telegram)."""
    from apps.api.models import ApiToken

    from .models import DeviceSession
    rows = DeviceSession.objects.filter(user=user).exclude(session_key=current_key or '-')
    keys = list(rows.values_list('session_key', flat=True))
    Session.objects.filter(session_key__in=keys).delete()
    n = len(keys)
    rows.delete()
    tokens = ApiToken.objects.filter(user=user)
    if current_token is not None:
        tokens = tokens.exclude(pk=current_token.pk)
    n += tokens.count()
    tokens.delete()
    from .models import DeviceAccount  # «запомненные входы» для переключения аккаунтов — тоже сбрасываем
    DeviceAccount.objects.filter(user=user).delete()
    return n


# ---------- вход по QR-коду ----------

def _qr_key(token: str) -> str:
    return f'qrlogin:{token}'


def qr_new(request) -> str:
    """Новый код для этого браузера. Старый код этого же браузера гаснет."""
    old = request.session.get('qr')
    if old:
        cache.delete(_qr_key(old))
    token = secrets.token_urlsafe(24)
    cache.set(_qr_key(token), {'uid': None, 'ua': describe(request.META.get('HTTP_USER_AGENT', '')), 'ip': _ip(request) or '',
                               'at': timezone.now().isoformat()}, QR_TTL)
    request.session['qr'] = token
    return token


def qr_image(url: str) -> str:
    """QR-код картинкой (data-URI) — без внешних сервисов."""
    import qrcode
    img = qrcode.make(url, border=2)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def qr_info(token: str):
    """Что за устройство просит вход (для экрана подтверждения) или None, если код устарел."""
    if not token or len(token) > 60:
        return None
    return cache.get(_qr_key(token))


def qr_approve(token: str, user) -> bool:
    data = qr_info(token)
    if data is None or data.get('uid'):
        return False
    cache.set(_qr_key(token), {**data, 'uid': user.pk}, 60)       # у компьютера минута, чтобы забрать вход
    return True


def qr_take(request):
    """Компьютер спрашивает «подтвердили?». Возвращает ('wait' | 'expired' | 'ok', человек). Вход отдаётся один раз
    и только тому браузеру, который показал код."""
    from django.contrib.auth import get_user_model
    token = request.session.get('qr')
    data = qr_info(token) if token else None
    if data is None:
        return 'expired', None
    if not data.get('uid'):
        return 'wait', None
    cache.delete(_qr_key(token))
    request.session.pop('qr', None)
    user = get_user_model().objects.filter(pk=data['uid'], is_active=True).first()
    return ('ok', user) if user is not None else ('expired', None)
