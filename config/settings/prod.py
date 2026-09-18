"""Прод: VPS в Docker (app + nginx) за Cloudflare. R2-медиа подключим позже (§5.5)."""
from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

# Прод не стартует с дев-заглушкой секрета — только настоящий ключ из .env
if 'dev-insecure' in SECRET_KEY:
    raise ImproperlyConfigured('Прод требует настоящий SECRET_KEY в .env')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# WhiteNoise: статику отдаёт приложение из /staticfiles (собирает entrypoint)
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# Когда появится HTTPS (Cloudflare) — включить:
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
