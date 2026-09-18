"""Дев-настройки: локальная машина разработчика."""
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# WhiteNoise в деве: без сборки статики в staticfiles/ (runserver отдаёт сам)
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True
