"""Общие настройки ilm4. Отличия дев/прода — в dev.py и prod.py (ARCHITECTURE.md §1)."""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    # Дев-запас без Docker: если DATABASE_URL не задан — SQLite.
    DATABASE_URL=(str, 'sqlite:///db.sqlite3'),
)
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY', default='dev-insecure-key')  # прод — обязательно из .env
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # сторонние
    'solo',
    'django_otp',
    'django_otp.plugins.otp_totp',
    # ilm4
    'apps.core',
    'apps.accounts',
    'apps.wallet',
    'apps.prayer',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'apps.accounts.middleware.Staff2FARequired',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.site',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': env.db('DATABASE_URL'),
}
# SQLite (дев-запас без Docker): ждём блокировку, а не падаем сразу
if DATABASES['default']['ENGINE'].endswith('sqlite3'):
    DATABASES['default'].setdefault('OPTIONS', {})
    DATABASES['default']['OPTIONS'].setdefault('timeout', 20)

# Единый пользователь платформы (PASSPORT §7.2). Кастомная модель — с первого дня.
AUTH_USER_MODEL = 'accounts.User'

# Вход по email (основной) + стандартный бэкенд (админка по логину)
AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# 2FA (TOTP): название в приложении-аутентификаторе
OTP_TOTP_ISSUER = 'ilm4'

LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Кэш: локальная память, пока Redis не понадобится (фаза карт/чата).
CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}

LOCALE_PATHS = [BASE_DIR / 'locale']
