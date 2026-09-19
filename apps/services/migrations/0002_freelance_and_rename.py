"""Фриланс в услугах + видимое имя раздела «Услуги · фриланс»."""
from django.db import migrations, models


def rename_module(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.filter(key='services').update(name='Услуги · фриланс')


def rename_back(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.filter(key='services').update(name='Услуги и переводы')


class Migration(migrations.Migration):
    dependencies = [
        ('services', '0001_initial'),
        ('core', '0006_sitesettings_boost_price_and_more'),
    ]
    operations = [
        migrations.AlterField(
            model_name='service',
            name='kind',
            field=models.CharField(
                choices=[
                    ('translate', 'Переводы документов (нотариальные)'),
                    ('lawyer', 'Исламский юрист / консультация'),
                    ('freelance', 'Фриланс: удалённая работа'),
                    ('tour', 'Туры: хадж и умра'),
                    ('other', 'Другая услуга'),
                ],
                max_length=12, verbose_name='вид'),
        ),
        migrations.RunPython(rename_module, rename_back),
    ]
