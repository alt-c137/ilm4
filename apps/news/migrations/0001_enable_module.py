"""Включаем контент-разделы фазы 6."""
from django.db import migrations


def enable(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    for key in ('news', 'forum', 'jobs', 'migration', 'services', 'library'):
        ModuleConfig.objects.update_or_create(key=key, defaults={'status': 'on'})


def disable(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.filter(key__in=('news', 'forum', 'jobs', 'migration',
                                         'services', 'library')).update(status='soon')


class Migration(migrations.Migration):
    dependencies = [('core', '0006_sitesettings_boost_price_and_more')]
    operations = [migrations.RunPython(enable, disable)]
