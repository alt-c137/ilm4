"""Сидинг: 6 палитр «Апп» из дизайн-макета + разделы платформы (все «скоро»)."""
from django.db import migrations

THEMES = [
    # (название, accent, accent_d, accent_soft) — из переключателя макета
    ('Фиолет', '#6d5efc', '#5646e8', '#ece9ff'),
    ('Океан', '#0ea5e9', '#0284c7', '#e0f2fe'),
    ('Мята', '#10b981', '#059669', '#d1fae5'),
    ('Коралл', '#f97316', '#ea580c', '#ffedd5'),
    ('Роза', '#ec4899', '#db2777', '#fce7f3'),
    ('Индиго', '#4f46e5', '#4338ca', '#e0e7ff'),
]

MODULES = [
    # (ключ, название, иконка, порядок). Статус по умолчанию — «скоро»;
    # фазы разработки переключают нужные в «on».
    ('prayer', 'Время намаза', '🕌', 10),
    ('learn', 'Обучение языкам', '📖', 20),
    ('buy', 'Купля-продажа', '🛒', 30),
    ('map', 'Карта халяль и врачей', '🗺️', 40),
    ('health', 'Здоровье', '🩺', 50),
    ('nikah', 'Никах', '💍', 60),
    ('finance', 'Финансы', '💱', 70),
    ('digital', 'Цифровые услуги', '💻', 80),
    ('jobs', 'Работа', '💼', 90),
    ('realestate', 'Недвижимость', '🏠', 100),
    ('migration', 'Миграция', '✈️', 110),
    ('services', 'Услуги и переводы', '📄', 120),
    ('news', 'Новости', '📰', 130),
    ('forum', 'Форум', '💬', 140),
    ('library', 'Библиотека', '📚', 150),
    ('chat', 'Чат', '💬', 160),
    ('invest', 'Инвестиции', '📈', 170),
    ('sport', 'Спорт', '⚽', 180),
]


def seed(apps, schema_editor):
    Theme = apps.get_model('core', 'Theme')
    ModuleConfig = apps.get_model('core', 'ModuleConfig')
    SiteSettings = apps.get_model('core', 'SiteSettings')

    for i, (name, accent, accent_d, accent_soft) in enumerate(THEMES):
        Theme.objects.get_or_create(
            name=name,
            defaults={'accent': accent, 'accent_d': accent_d,
                      'accent_soft': accent_soft, 'order': i},
        )
    for key, name, icon, order in MODULES:
        ModuleConfig.objects.get_or_create(
            key=key, defaults={'name': name, 'icon': icon, 'order': order},
        )

    # get_solo() — метод живой модели, исторической он недоступен; singleton —
    # единственная запись, создаём при необходимости.
    settings = SiteSettings.objects.first()
    if settings is None:
        settings = SiteSettings.objects.create()
    if not settings.default_theme_id:
        settings.default_theme = Theme.objects.order_by('order').first()
        settings.save()


def unseed(apps, schema_editor):
    pass  # сид-данные безвредны, не убираем


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(seed, unseed),
    ]
