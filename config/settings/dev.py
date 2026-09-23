"""Дев-настройки: локальная машина разработчика."""
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# WhiteNoise в деве: без сборки статики в staticfiles/ (runserver отдаёт сам)
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True

# Локальный запуск через туннель (scripts/run_local.sh → https://*.trycloudflare.com):
# туннель передаёт X-Forwarded-Proto=https — без этого формы на https-адресе упадут с ошибкой CSRF
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS, 'https://*.trycloudflare.com']
