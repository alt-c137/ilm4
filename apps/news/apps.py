from django.apps import AppConfig


class NewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.news'
    verbose_name = 'Новости'

    def ready(self):
        from apps.core.blocks import register_block

        register_block(key='news_recent', template='news/blocks/recent.html', order=75)
