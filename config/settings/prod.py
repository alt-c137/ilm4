"""Прод: VPS в Docker (app + nginx) за Cloudflare. R2-медиа подключим позже (§5.5)."""
from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

# Прод не стартует с дев-заглушкой секрета — только настоящий ключ из .env
if 'dev-insecure' in SECRET_KEY:
    raise ImproperlyConfigured('Прод требует настоящий SECRET_KEY в .env')
# Переписка шифруется главным ключом — без него в проде не стартуем (иначе ключ зависел бы от SECRET_KEY)
if not env('CHAT_MASTER_KEYS', default=''):
    raise ImproperlyConfigured('Прод требует CHAT_MASTER_KEYS в .env: python manage.py chat_keys generate '
                               '(и сразу сделайте резервную копию: chat_keys split)')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# Настоящий адрес посетителя: перед приложением всегда nginx, он кладёт проверенный адрес в X-Real-IP
# (nginx/ilm4.conf; за Cloudflare — только с адресов самого Cloudflare). См. apps/core/limits.py: client_ip.
CLIENT_IP_HEADER = 'HTTP_X_REAL_IP'

# HTTPS-пакет: включается одной переменной SECURE_SSL=True в .env,
# когда сайт встанет за Cloudflare с сертификатом (до этого — False, по http).
if env('SECURE_SSL', default=False):
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000      # год Strict Transport Security
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# WhiteNoise: статику отдаёт приложение из /staticfiles (собирает entrypoint)
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# Вложения чата отдаёт nginx после проверки участника в Django (location /protected-media/)
CHAT_XACCEL = env('CHAT_XACCEL', default=True)

# Набор готовых соединений с базой вместо «новое соединение на каждый запрос» — быстрее под нагрузкой.
# Включается DB_POOL=True в .env (нужен пакет psycopg[pool], он в requirements).
if env('DB_POOL', default=False):
    DATABASES['default'].setdefault('OPTIONS', {})['pool'] = {'min_size': 2, 'max_size': env.int('DB_POOL_MAX', default=12)}

# django-solo: «Настройки сайта» читаются на каждой странице — держим их в общем кеше (Redis),
# сохранение в админке сразу его сбрасывает.
SOLO_CACHE = 'default'
SOLO_CACHE_TIMEOUT = 300
