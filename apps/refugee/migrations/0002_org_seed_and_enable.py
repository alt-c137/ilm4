"""Демо-справочник УВКБ (офисы с сайтами; телефоны вносит админ проверенными)
и включение раздела «Помощь беженцам»."""
from django.db import migrations

ORGS = [
    # (страна, город, название, тип, сайт, примечание)
    ('Турция', 'Анкара', 'УВКБ ООН в Турции (представительство)', 'unhcr',
     'https://www.unhcr.org/tr', 'Региональное представительство. Приём по записи.'),
    ('Казахстан', 'Астана', 'УВКБ ООН в Казахстане', 'unhcr',
     'https://help.unhcr.org/kazakhstan', 'Информация для лиц, ищущих убежище.'),
    ('Узбекистан', 'Ташкент', 'УВКБ ООН — офис связи в Узбекистане', 'unhcr',
     'https://www.unhcr.org/uzbekistan', 'Приём обращений по предварительной записи.'),
    ('Россия', 'Москва', 'УВКБ ООН в Российской Федерации', 'unhcr',
     'https://help.unhcr.org/russianfederation', 'Консультации по документам и статусу.'),
    ('Германия', 'Нюрнберг', 'BAMF — Федеральное ведомство по делам миграции', 'other',
     'https://www.bamf.de', 'Подача заявлений на убежище (раздел Asyl).'),
]


def seed(apps, schema_editor):
    Org = apps.get_model('refugee', 'Org')
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    for country, city, name, kind, site, notes in ORGS:
        Org.objects.get_or_create(
            name=name,
            defaults={'country': country, 'city': city, 'kind': kind,
                      'website': site, 'notes': notes + ' Телефоны уточняйте на сайте.'},
        )
    ModuleConfig.objects.update_or_create(
        key='refugee', defaults={'name': 'Помощь беженцам', 'icon': '🕊️', 'status': 'on'})


def unseed(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.filter(key='refugee').update(status='soon')


class Migration(migrations.Migration):
    dependencies = [
        ('refugee', '0001_initial'),
        ('core', '0006_sitesettings_boost_price_and_more'),
    ]
    operations = [
        migrations.RunPython(seed, unseed),
    ]
