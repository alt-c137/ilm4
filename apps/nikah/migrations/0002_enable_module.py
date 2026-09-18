"""Включаем раздел «Никах»."""
from django.db import migrations


def enable(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.update_or_create(key='nikah', defaults={'status': 'on'})


def disable(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.filter(key='nikah').update(status='soon')


class Migration(migrations.Migration):
    dependencies = [('nikah', '0001_initial')]
    operations = [migrations.RunPython(enable, disable)]
