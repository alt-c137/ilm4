from django.apps import AppConfig


class MapsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.maps'
    verbose_name = 'Карта'

    def ready(self):
        from apps.core.blocks import register_block

        register_block(key='map_recent', template='maps/blocks/recent.html', order=35)
