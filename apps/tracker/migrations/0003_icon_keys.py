"""Значки привычек и общих трекеров: вместо эмодзи — ключи SVG-значков (тег {% hicon %}). Старые эмодзи переводим в ключи."""
from django.db import migrations, models

MAP = {'✅': 'h-check', '💊': 'h-pill', '💧': 'h-water', '📖': 'h-quran', '🕌': 'h-mosque', '🤲': 'h-dua', '🏃': 'h-run', '🧘': 'h-mind',
       '🥗': 'h-food', '😴': 'h-sleep', '📚': 'h-books', '✍️': 'h-write', '✍': 'h-write', '🗣': 'h-speak', '🗣️': 'h-speak', '💼': 'h-work',
       '🧹': 'h-clean', '💰': 'h-money', '📵': 'h-nophone', '🌙': 'h-moon', '☀️': 'h-sun', '☀': 'h-sun', '🎯': 'h-target', '🤝': 'h-together',
       '🌅': 'h-sunrise', '✨': 'h-star', '🚶': 'h-walk', '🏋️': 'h-sport', '🏋': 'h-sport', '🔤': 'h-lang', '📅': 'h-meet'}


def forward(apps, schema_editor):
    for name, default in (('Habit', 'h-check'), ('Board', 'h-together')):
        model = apps.get_model('tracker', name)
        for row in model.objects.all().only('id', 'emoji'):
            key = MAP.get(row.emoji) or (row.emoji if row.emoji.startswith('h-') else default)
            if key != row.emoji:
                model.objects.filter(pk=row.pk).update(emoji=key)


class Migration(migrations.Migration):
    dependencies = [('tracker', '0002_v49')]
    operations = [
        migrations.AlterField('board', 'emoji', models.CharField('значок', max_length=16, default='h-together')),
        migrations.AlterField('habit', 'emoji', models.CharField('значок', max_length=16, default='h-check')),
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
