"""Прод: VPS в Docker (app + nginx) за Cloudflare. R2-медиа подключим позже (§5.5)."""
from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

# Прод не стартует с дев-заглушкой секрета — только настоящий ключ из .env
if 'dev-insecure' in SECRET_KEY:
    raise ImproperlyConfigured('Прод требует настоящий SECRET_KEY в .env')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

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
