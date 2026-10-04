from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = 'Аккаунты'

    def ready(self):
        # Сигналы журнала действий (вход/выход админов)
        # «Устройства»: каждый вход на сайт — строка в списке активных сеансов, выход — убирает её
        from django.contrib.auth.signals import user_logged_in, user_logged_out

        from . import (
            audit,  # noqa: F401
            photo_signals,  # noqa: F401 — история фото профиля
        )

        def _in(sender, request, user, **kwargs):
            if request is not None and hasattr(request, 'session'):
                from . import devices
                devices.record(request, user)

        def _out(sender, request, user, **kwargs):
            key = getattr(getattr(request, 'session', None), 'session_key', None)
            if key:
                from . import devices
                devices.forget(key)

        user_logged_in.connect(_in, weak=False, dispatch_uid='accounts_device_in')
        user_logged_out.connect(_out, weak=False, dispatch_uid='accounts_device_out')
