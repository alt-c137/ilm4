"""Разделы книг."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('library', '0001_initial'),
    ]
    operations = [
        migrations.AddField(
            model_name='book',
            name='category',
            field=models.CharField(
                choices=[
                    ('akida', 'Акыда'), ('fiqh', 'Фикх'), ('quran', 'Коран и таджвид'),
                    ('arabic', 'Арабский язык'), ('history', 'История Ислама'),
                    ('family', 'Семья и воспитание'), ('other', 'Другое'),
                ],
                default='other', max_length=20, verbose_name='раздел'),
        ),
    ]
