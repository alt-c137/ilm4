"""Раздел «ИИ-помощник» — включён: без ключа площадки работает со своим ключом человека."""
from django.db import migrations


def forward(apps, schema_editor):
    apps.get_model('core', 'ModuleConfig').objects.get_or_create(
        key='assistant', defaults={'name': 'ИИ-помощник', 'icon': '✨', 'order': 3, 'status': 'on', 'in_grid': True})


def backward(apps, schema_editor):
    apps.get_model('core', 'ModuleConfig').objects.filter(key='assistant').delete()


class Migration(migrations.Migration):
    dependencies = [('core', '0039_sitesettings_assistant_daily_free')]
    operations = [migrations.RunPython(forward, backward)]
