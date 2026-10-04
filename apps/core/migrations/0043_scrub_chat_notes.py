"""Убрать из уведомлений начало текста личных сообщений.

Переписка в базе зашифрована, а в таблице уведомлений раньше лежало «Имя: первые 80 знаков сообщения» открытым
текстом. Теперь туда пишется только «Имя: новое сообщение» (apps/chat/events.py: quiet_note); здесь чистим старое."""
import re

from django.db import migrations

CHAT_URL = re.compile(r'^/chat/\d+/(post/\d+/)?$')


def scrub(apps, schema_editor):
    Notification = apps.get_model('core', 'Notification')
    for note in Notification.objects.filter(url__startswith='/chat/').iterator():
        name, sep, _rest = note.text.partition(': ')
        if not sep or not CHAT_URL.match(note.url) or name.startswith('Вас позвали'):
            continue
        Notification.objects.filter(pk=note.pk).update(text=f'{name[:80]}: новое сообщение')


class Migration(migrations.Migration):
    dependencies = [('core', '0042_ads')]
    operations = [migrations.RunPython(scrub, migrations.RunPython.noop)]
