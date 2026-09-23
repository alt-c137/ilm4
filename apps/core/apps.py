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
        # rates: курс валют переехал в инфопанель героя (v26), отдельной полосой больше не показываем
        register_block(key='banner', template='core/blocks/banner.html', order=12)
        register_block(key='modules', template='core/blocks/modules.html', order=20)
        register_block(key='basics', template='core/blocks/basics.html', order=25)
        register_block(key='support', template='core/blocks/support.html', order=90)
