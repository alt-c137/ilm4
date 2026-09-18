from django.apps import AppConfig


class PrayerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.prayer'
    verbose_name = 'Время намаза'

    def ready(self):
        # Блок на главную сразу после hero (§3.2)
        from apps.core.blocks import register_block

        register_block(key='prayer_widget', template='prayer/blocks/widget.html', order=15)
