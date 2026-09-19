"""Разделы вакансий."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0001_initial'),
    ]
    operations = [
        migrations.AddField(
            model_name='vacancy',
            name='category',
            field=models.CharField(
                choices=[
                    ('it', 'IT и интернет'), ('drive', 'Вождение и доставка'),
                    ('build', 'Строительство'), ('med', 'Медицина'),
                    ('edu', 'Образование'), ('trade', 'Торговля'), ('other', 'Другое'),
                ],
                default='other', max_length=20, verbose_name='раздел'),
        ),
    ]
