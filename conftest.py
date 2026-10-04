"""Общие настройки тестов: тесты не зависят от локального .env разработчика."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_settings(settings, tmp_path):
    # файлы из тестов (фото анкет, вложения чатов) — во временную папку, а не в настоящую media/
    settings.MEDIA_ROOT = tmp_path / 'media'
    # бот из .env включил бы проверку номера и запросы в Telegram — в тестах его нет,
    # тесты, которым бот нужен, включают его сами (фикстура bot в apps/core/tests/test_moderation.py)
    settings.TELEGRAM_BOT_TOKEN = ''
    settings.TELEGRAM_BOT_USERNAME = ''
    settings.TELEGRAM_MODERATION_CHAT_ID = ''
    settings.GOOGLE_OAUTH_CLIENT_ID = ''
    settings.GOOGLE_OAUTH_CLIENT_SECRET = ''
    settings.FX_AUTO_REFRESH = False      # курсы валют: в тестах в сеть не ходим
    settings.WELCOME_SCREEN = False       # экран первого входа («дизайн и рабочий стол») — отдельный тест включает его сам
    from django.core.cache import cache

    from apps.chat import keyring
    from apps.core import fx
    cache.clear()                 # счётчики лимитов из прошлого теста не должны влиять на следующий
    keyring.forget_cache()        # ключи чатов из прошлого теста (другая база) не переиспользуем
    fx.forget()
    yield
    keyring.forget_cache()
