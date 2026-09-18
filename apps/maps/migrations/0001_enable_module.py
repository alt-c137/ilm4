"""Включаем разделы «Карта» и «Здоровье»."""
from django.db import migrations


def enable(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    for key in ('map', 'health'):
        ModuleConfig.objects.update_or_create(key=key, defaults={'status': 'on'})


def disable(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.filter(key__in=('map', 'health')).update(status='soon')


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_sitesettings_prayer_method'),
    ]
    operations = [
        migrations.RunPython(enable, disable),
    ]
