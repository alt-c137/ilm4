"""Раздел «Сообщества» (как серверы в Discord) — включён."""
from django.db import migrations


def forward(apps, schema_editor):
    apps.get_model('core', 'ModuleConfig').objects.get_or_create(
        key='communities', defaults={'name': 'Сообщества', 'icon': '', 'order': 4, 'status': 'on', 'in_grid': True})


def backward(apps, schema_editor):
    apps.get_model('core', 'ModuleConfig').objects.filter(key='communities').delete()


class Migration(migrations.Migration):
    dependencies = [('core', '0040_module_assistant')]
    operations = [migrations.RunPython(forward, backward)]
