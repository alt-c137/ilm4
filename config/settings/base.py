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
    'django.contrib.humanize',
    'daphne',   # ASGI-runserver (WebSocket чата); обязан стоять до staticfiles
    'django.contrib.staticfiles',
    # сторонние
    'solo',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'taggit',
    'channels',
    # ilm4
    'apps.core',
    'apps.accounts',
    'apps.wallet',
    'apps.prayer',
    'apps.maps',
    'apps.health',
    'apps.market',
    'apps.news',
    'apps.forum',
    'apps.jobs',
    'apps.migration',
    'apps.services',
    'apps.library',
    'apps.nikah',
    'apps.chat',
    'apps.refugee',
    'apps.transport',
    'apps.reviews',
    'apps.deals',
    'apps.payments',
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
ASGI_APPLICATION = 'config.asgi.application'

# Real-time (чат): Redis на проде; в деве без Redis — слой в памяти
CHANNEL_LAYERS = {
    'default': (
        {'BACKEND': 'channels_redis.core.RedisChannelLayer',
         'CONFIG': [{'url': env('REDIS_URL')}]}
        if env('REDIS_URL', default='') else
        {'BACKEND': 'channels.layers.InMemoryChannelLayer'}
    ),
}

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

# Вход через Google (apps/accounts/google.py): ключи из Google Cloud Console
GOOGLE_OAUTH_CLIENT_ID = env('GOOGLE_OAUTH_CLIENT_ID', default='')
GOOGLE_OAUTH_CLIENT_SECRET = env('GOOGLE_OAUTH_CLIENT_SECRET', default='')

# Режим сайта: full — вся платформа; nikah — отдельная установка только раздела «Никях»
# (главная ведёт в никях, остальные разделы закрыты). См. docs/LAUNCH.md §7.
SITE_MODE = env('SITE_MODE', default='full')
NIKAH_MODE_KEYS = {'nikah', 'chat', 'wallet'}   # разделы, которые нужны никяху

# Telegram: мини-приложение (вход из Telegram) и уведомления бота. Токен — от @BotFather
TELEGRAM_BOT_TOKEN = env('TELEGRAM_BOT_TOKEN', default='')
TELEGRAM_BOT_USERNAME = env('TELEGRAM_BOT_USERNAME', default='')   # без @, для ссылки «Открыть в Telegram»
# Адрес сайта для ссылок в уведомлениях (кнопка «Открыть» в Telegram — только https)
SITE_URL = env('SITE_URL', default='')

# Шифрование переписки в БД (apps/chat/crypto.py). В проде — свой ключ и его резервная копия!
CHAT_ENCRYPTION_KEY = env('CHAT_ENCRYPTION_KEY', default='')

# Платёжные провайдеры (apps/payments/providers.py): способ включается, когда заданы ключи
PAYME_MERCHANT_ID = env('PAYME_MERCHANT_ID', default='')
PAYME_SECRET = env('PAYME_SECRET', default='')
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default='')
CRYPTO_GATEWAY_KEY = env('CRYPTO_GATEWAY_KEY', default='')
CRYPTO_GATEWAY_SECRET = env('CRYPTO_GATEWAY_SECRET', default='')
# Почта (восстановление пароля). В деве письма печатаются в консоль.
# Прод: EMAIL_URL=smtp+tls://логин:пароль@smtp.сервис.com:587 (пароль — url-кодированный)
vars().update(env.email_url('EMAIL_URL', default='consolemail://'))
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='ilm4 <noreply@ilm4.com>')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

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

# Пароли: не короче 8 символов, не из списка популярных, не только цифры
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Кэш: в проде — Redis (общий для всех процессов: лимиты входа, контактов);
# в деве без Redis — локальная память.
CACHES = {
    'default': (
        {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': env('REDIS_URL')}
        if env('REDIS_URL', default='') else
        {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}
    ),
}

LOCALE_PATHS = [BASE_DIR / 'locale']
