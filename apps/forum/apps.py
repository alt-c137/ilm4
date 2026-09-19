from django.apps import AppConfig


class ForumConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.forum'
    verbose_name = 'Форум'

    def ready(self):
        from apps.core.blocks import register_block

        register_block(key='forum_recent', template='forum/blocks/recent.html', order=70)
