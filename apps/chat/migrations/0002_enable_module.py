"""Включаем чат."""
from django.db import migrations


def enable(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.update_or_create(key='chat', defaults={'status': 'on'})


def disable(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.filter(key='chat').update(status='soon')


class Migration(migrations.Migration):
    dependencies = [('chat', '0001_initial')]
    operations = [migrations.RunPython(enable, disable)]
