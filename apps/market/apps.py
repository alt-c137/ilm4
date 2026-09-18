from django.apps import AppConfig


class MarketConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.market'
    verbose_name = 'ilmbuy — купля-продажа'

    def ready(self):
        from apps.core.blocks import register_block

        register_block(key='market_recent', template='market/blocks/recent.html', order=30)
