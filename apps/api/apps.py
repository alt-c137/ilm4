from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.api'
    verbose_name = 'API мобильного приложения'

    def ready(self):
        from . import push  # noqa: F401  — пуш на телефон при каждом уведомлении
