"""Кошелёк — раздел в ModuleConfig: включается/выключается в админке."""
from django.db import migrations


def forward(apps, schema_editor):
    M = apps.get_model('core', 'ModuleConfig')
    M.objects.get_or_create(key='wallet', defaults={'name': 'Кошелёк', 'icon': '💰', 'order': 175,
                                                    'status': 'on', 'in_grid': False})


def backward(apps, schema_editor):
    apps.get_model('core', 'ModuleConfig').objects.filter(key='wallet').delete()


class Migration(migrations.Migration):
    dependencies = [('core', '0013_wallet_payouts_flag')]
    operations = [migrations.RunPython(forward, backward)]
