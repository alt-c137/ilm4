"""Зашифровать уже существующие сообщения (поле само шифрует при сохранении)."""
from django.db import migrations


def forward(apps, schema_editor):
    Message = apps.get_model('chat', 'Message')
    for m in Message.objects.all().iterator():
        m.save(update_fields=['body'])


class Migration(migrations.Migration):
    dependencies = [('chat', '0005_encrypt_body')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
