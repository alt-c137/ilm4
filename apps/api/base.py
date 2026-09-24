"""Каркас API приложения: вход по токену, язык, JSON, ошибки, выключатели разделов.

Сессии и куки здесь не используются вовсе — только заголовок
`Authorization: Bearer <токен>`. Поэтому CSRF не нужен: чужой сайт не может
подставить токен, который лежит только в защищённом хранилище телефона.
"""
import json
from functools import wraps

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt

PAGE_SIZE = 20

# раздел приложения → ключ ModuleConfig (выключен в админке — пропадает и в приложении)
MODULE_OF = {'buy': 'buy', 'jobs': 'jobs', 'services': 'services', 'transport': 'transport', 'places': 'map',
             'doctors': 'health', 'stories': 'migration', 'books': 'library', 'topics': 'forum', 'news': 'news',
             'nikah': 'nikah', 'chat': 'chat', 'wallet': 'wallet', 'prayer': 'prayer'}


class ApiError(Exception):
    def __init__(self, message, status=400, code=''):
        super().__init__(str(message))
        self.message, self.status, self.code = str(message), status, code


def bearer(request) -> str:
    h = request.headers.get('Authorization', '')
    return h[7:].strip() if h.startswith('Bearer ') else ''


def _lang(request, user) -> str:
    langs = dict(settings.LANGUAGES)
    for code in (request.headers.get('X-Lang', ''), getattr(user, 'language', '') or '',
                 request.headers.get('Accept-Language', '')[:2]):
        code = (code or '').lower()[:2]
        if code in langs:
            return code
    return settings.LANGUAGE_CODE


def module_on(key: str) -> bool:
    from apps.core.models import ModuleConfig
    if settings.SITE_MODE == 'nikah' and key not in settings.NIKAH_MODE_KEYS:
        return False
    return ModuleConfig.objects.filter(key=key, status=ModuleConfig.ON).exists()


def _cors(response):
    """API без кук (только токен в заголовке) — открывать для любых источников безопасно:
    чужая страница не получит ничего, чего не может получить и без браузера."""
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, X-Lang, Accept-Language'
    response['Access-Control-Allow-Methods'] = 'GET, POST, PATCH, DELETE, OPTIONS'
    response['Access-Control-Max-Age'] = '86400'
    return response


def api(methods=('GET',), auth=False, module=None):
    """Декоратор: метод, вход по токену, раздел включён, язык, JSON-ответ и ошибки."""
    def deco(view):
        @csrf_exempt
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method == 'OPTIONS':
                from django.http import HttpResponse
                return _cors(HttpResponse(status=204))
            return _cors(_run(view, request, *args, **kwargs))

        def _run(view, request, *args, **kwargs):
            from .models import ApiToken

            if request.method not in methods:
                return JsonResponse({'error': 'method'}, status=405)
            tok = ApiToken.lookup(bearer(request))
            request.user = tok.user if tok else AnonymousUser()
            request.api_token = tok
            with translation.override(_lang(request, request.user)):
                if auth and not request.user.is_authenticated:
                    return JsonResponse({'error': _('Войдите в аккаунт'), 'code': 'auth'}, status=401)
                if module and not module_on(MODULE_OF.get(module, module)):
                    return JsonResponse({'error': _('Раздел сейчас выключен'), 'code': 'module_off'}, status=404)
                request.data = {}
                if request.content_type == 'application/json' and request.body:
                    try:
                        request.data = json.loads(request.body)
                    except ValueError:
                        return JsonResponse({'error': 'json'}, status=400)
                    if not isinstance(request.data, dict):
                        return JsonResponse({'error': 'json'}, status=400)
                elif request.method == 'POST':
                    request.data = request.POST
                try:
                    result = view(request, *args, **kwargs)
                except ApiError as e:
                    return JsonResponse({'error': e.message, 'code': e.code}, status=e.status)
                except Http404:
                    return JsonResponse({'error': _('Не найдено'), 'code': 'not_found'}, status=404)
                except PermissionDenied:
                    return JsonResponse({'error': _('Нет доступа'), 'code': 'forbidden'}, status=403)
                except ValidationError as e:
                    return JsonResponse({'error': ' '.join(e.messages)}, status=400)
                if isinstance(result, (dict, list)):
                    return JsonResponse(result, safe=False, json_dumps_params={'ensure_ascii': False})
                return result
        return wrapped
    return deco


def page(request, qs, fn):
    """Постранично: ?page=1… → {'items': […], 'next': номер или null}."""
    try:
        n = max(1, min(int(request.GET.get('page', 1)), 500))
    except ValueError:
        n = 1
    start = (n - 1) * PAGE_SIZE
    chunk = list(qs[start:start + PAGE_SIZE + 1])
    return {'items': [fn(x) for x in chunk[:PAGE_SIZE]], 'next': n + 1 if len(chunk) > PAGE_SIZE else None}


def abs_url(request, path: str) -> str:
    if not path:
        return ''
    if path.startswith('http'):
        return path
    base = getattr(settings, 'SITE_URL', '') or ''
    return (base.rstrip('/') + path) if base.startswith('http') else request.build_absolute_uri(path)


def file_url(request, f) -> str:
    try:
        return abs_url(request, f.url) if f else ''
    except ValueError:
        return ''


def limit(key: str, max_hits: int, window: int) -> None:
    """Ограничение частоты (против перебора и спама). Превышено — 429."""
    from django.core.cache import cache
    cache.add(key, 0, window)
    try:
        hits = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)
        hits = 1
    if hits > max_hits:
        raise ApiError(_('Слишком часто — подождите немного.'), 429, 'rate')


def as_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
