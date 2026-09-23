"""Новые разделы «Развлечения» и «Адвокаты» — пока со статусом «скоро»
(видны в каталоге сервисов; включаются в админке, когда будут готовы)."""
from django.db import migrations

NEW = [
    ('lawyers', 'Адвокаты', '⚖️', 185),
    ('fun', 'Развлечения', '🎉', 190),
]


def forward(apps, schema_editor):
    M = apps.get_model('core', 'ModuleConfig')
    for key, name, icon, order in NEW:
        M.objects.get_or_create(key=key, defaults={'name': name, 'icon': icon, 'order': order,
                                                   'status': 'soon', 'in_grid': True})


def backward(apps, schema_editor):
    apps.get_model('core', 'ModuleConfig').objects.filter(key__in=[k for k, *_ in NEW]).delete()


class Migration(migrations.Migration):
    dependencies = [('core', '0009_banner_duration_seconds_sitesettings_hadis_details')]
    operations = [migrations.RunPython(forward, backward)]
