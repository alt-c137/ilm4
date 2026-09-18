"""Включаем раздел «Время намаза» — первый живой раздел платформы."""
from django.db import migrations


def enable(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.update_or_create(
        key='prayer', defaults={'status': 'on'},
    )


def disable(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.filter(key='prayer').update(status='soon')


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_sitesettings_min_payout'),
    ]
    operations = [
        migrations.RunPython(enable, disable),
    ]
