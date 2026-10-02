"""Новый раздел «Трекер привычек» — сразу включён (выключается в админке, как любой раздел)."""
from django.db import migrations


def forward(apps, schema_editor):
    M = apps.get_model('core', 'ModuleConfig')
    M.objects.get_or_create(key='tracker', defaults={'name': 'Трекер привычек', 'icon': '🎯', 'order': 35,
                                                     'status': 'on', 'in_grid': True})


def backward(apps, schema_editor):
    apps.get_model('core', 'ModuleConfig').objects.filter(key='tracker').delete()


class Migration(migrations.Migration):
    dependencies = [('core', '0036_rooms')]
    operations = [migrations.RunPython(forward, backward)]
