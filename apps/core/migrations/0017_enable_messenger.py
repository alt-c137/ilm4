"""Включить функции мессенджера в существующих настройках (выключаются в админке)."""
from django.db import migrations


def forward(apps, schema_editor):
    S = apps.get_model('core', 'SiteSettings')
    S.objects.update(chat_photos_enabled=True)


class Migration(migrations.Migration):
    dependencies = [('core', '0016_messenger_flags')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
