from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Ядро ilm4'

    def ready(self):
        # «Бомба» из картинки: файл в пару мегабайт, а при раскрытии — сотни мегабайт памяти. Pillow отказывает сам,
        # когда точек больше двух MAX_IMAGE_PIXELS (по умолчанию это ~180 Мп — слишком щедро). Ставим предел 50 Мп:
        # хватает снимкам с камер на 48–50 Мп; больше — отказ ещё при открытии файла, до раскрытия.
        # Действует на все загрузки картинок на сайте. Предупреждение «больше половины предела» нам не нужно.
        import warnings

        from PIL import Image
        Image.MAX_IMAGE_PIXELS = 25_000_000
        warnings.simplefilter('ignore', Image.DecompressionBombWarning)

        # Блоки главной ядра. Разделы зарегистрируют свои блоки
        # в собственных AppConfig.ready() (ARCHITECTURE.md §3.2).
        from . import signals
        from .blocks import register_block

        signals.connect()   # уведомления авторам об одобрении / отклонении

        register_block(key='hero', template='core/blocks/hero.html', order=10)
        # rates: курс валют переехал в инфопанель героя (v26), отдельной полосой больше не показываем
        register_block(key='banner', template='core/blocks/banner.html', order=27)
        register_block(key='modules', template='core/blocks/modules.html', order=20)
        register_block(key='basics', template='core/blocks/basics.html', order=25)
        register_block(key='support', template='core/blocks/support.html', order=90)
