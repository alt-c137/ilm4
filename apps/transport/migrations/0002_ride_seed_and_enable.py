"""Включение раздела «Перевозки» + демо-маршруты."""
from django.db import migrations


def seed(apps, schema_editor):
    Ride = apps.get_model('transport', 'Ride')
    User = apps.get_model('accounts', 'User')
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    demo, _ = User.objects.get_or_create(
        username='demo', defaults={'email': 'demo@ilm4.local'})
    rides = [
        ('Ташкент', 'Москва', 'cargo', 'от 1 500 000 сум, зависит от объёма',
         'Газель 3 т, регулярные рейсы раз в неделю. Попутный груз — скидка.'),
        ('Ташкент', 'Санкт-Петербург', 'pax', 'от 300 $ с человека',
         'Минивэн 7 мест, выезд по пятницам. Документы: паспорт.'),
        ('Казань', 'Уфа', 'both', 'договорная',
         'Попутчик: еду в субботу, места для 2 пассажиров и небольшой груз.'),
    ]
    for f, t, typ, price, desc in rides:
        Ride.objects.get_or_create(
            from_city=f, to_city=t, type=typ,
            defaults={'price_text': price, 'description': desc,
                      'contact': 'demo', 'owner': demo,
                      'status': 'approved'})
    ModuleConfig.objects.update_or_create(
        key='transport', defaults={'name': 'Перевозки', 'icon': '🚚', 'status': 'on'})


def unseed(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.filter(key='transport').update(status='soon')


class Migration(migrations.Migration):
    dependencies = [
        ('transport', '0001_initial'),
        ('core', '0006_sitesettings_boost_price_and_more'),
    ]
    operations = [
        migrations.RunPython(seed, unseed),
    ]
