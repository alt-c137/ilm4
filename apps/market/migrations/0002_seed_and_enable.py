"""Включаем ilmbuy и сеем категории объявлений."""
from django.db import migrations

CATEGORIES = [
    ('Электроника', 'electronics', '📱', 10),
    ('Авто', 'auto', '🚗', 20),
    ('Одежда и скромные платья', 'clothes', '👗', 30),
    ('Дом и сад', 'home', '🏡', 40),
    ('Детский мир', 'kids', '🧸', 50),
    ('Кулинария и халяль-еда', 'food', '🍲', 60),
    ('Услуги', 'services', '🔧', 70),
    ('Книги', 'books', '📚', 80),
    ('Другое', 'other', '📦', 90),
]


def seed(apps, schema_editor):
    Category = apps.get_model('market', 'Category')
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    for name, slug, icon, order in CATEGORIES:
        Category.objects.get_or_create(
            slug=slug, defaults={'name': name, 'icon': icon, 'order': order})
    ModuleConfig.objects.update_or_create(key='buy', defaults={'status': 'on'})


def unseed(apps, schema_editor):
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    ModuleConfig.objects.filter(key='buy').update(status='soon')


class Migration(migrations.Migration):
    dependencies = [
        ('market', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(seed, unseed),
    ]
