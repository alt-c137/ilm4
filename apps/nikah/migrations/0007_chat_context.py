"""Существующие чаты пар никяха помечаются типом «nikah» — попадают в папку «Никях»."""
from django.db import migrations


def mark(apps, schema_editor):
    Match = apps.get_model('nikah', 'NikahMatch')
    Thread = apps.get_model('chat', 'Thread')
    for m in Match.objects.exclude(thread__isnull=True).only('pk', 'thread_id'):
        Thread.objects.filter(pk=m.thread_id).update(context_type='nikah', context_id=m.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('nikah', '0006_witness'),
        ('chat', '0010_chat_context_files'),
    ]

    operations = [migrations.RunPython(mark, migrations.RunPython.noop)]
