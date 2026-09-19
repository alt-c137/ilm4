"""«Карта халяль и врачей» → «Халяль карта»."""
from django.db import migrations


def rename(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.filter(key='map').update(name='Халяль карта')


def rename_back(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.filter(key='map').update(name='Карта халяль и врачей')


class Migration(migrations.Migration):
    dependencies = [
        ('maps', '0002_initial'),
        ('core', '0006_sitesettings_boost_price_and_more'),
    ]
    operations = [
        migrations.RunPython(rename, rename_back),
    ]
