"""Прод: Contabo VPS за Cloudflare. Дополняется в фазе деплоя (R2, логирование, WhiteNoise)."""
from .base import *

DEBUG = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
