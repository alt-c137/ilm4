from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Ядро ilm4'

    def ready(self):
        # Блоки главной ядра. Разделы зарегистрируют свои блоки
        # в собственных AppConfig.ready() (ARCHITECTURE.md §3.2).
        from .blocks import register_block

        register_block(key='hero', template='core/blocks/hero.html', order=10)
        register_block(key='rates', template='core/blocks/rates.html', order=58)
        register_block(key='banner', template='core/blocks/banner.html', order=12)
        register_block(key='modules', template='core/blocks/modules.html', order=20)
        register_block(key='support', template='core/blocks/support.html', order=90)
