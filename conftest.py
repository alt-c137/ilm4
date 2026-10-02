"""Общие настройки тестов: тесты не зависят от локального .env разработчика."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_settings(settings):
    # бот из .env включил бы проверку номера и запросы в Telegram — в тестах его нет,
    # тесты, которым бот нужен, включают его сами (фикстура bot в apps/core/tests/test_moderation.py)
    settings.TELEGRAM_BOT_TOKEN = ''
    settings.TELEGRAM_BOT_USERNAME = ''
    settings.TELEGRAM_MODERATION_CHAT_ID = ''
    settings.GOOGLE_OAUTH_CLIENT_ID = ''
    settings.GOOGLE_OAUTH_CLIENT_SECRET = ''
    from apps.chat import keyring
    keyring.forget_cache()        # ключи чатов из прошлого теста (другая база) не переиспользуем
    yield
    keyring.forget_cache()
