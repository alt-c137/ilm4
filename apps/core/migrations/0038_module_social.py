"""Лента (как во ВКонтакте) — включена; сторис — включены (только фото); короткие видео и подарки — «скоро»:
основа готова, включаются в админке, когда будут мощности под видео и оплату подарков."""
from django.db import migrations

MODULES = [
    ('feed', 'Лента', '📰', 4, 'on'),
    ('stories', 'Сторис', '⭕', 5, 'on'),
    ('shorts', 'ilm4-shorts', '🎬', 6, 'soon'),
    ('gifts', 'Подарки', '🎁', 7, 'soon'),
]


def forward(apps, schema_editor):
    M = apps.get_model('core', 'ModuleConfig')
    for key, name, icon, order, status in MODULES:
        M.objects.get_or_create(key=key, defaults={'name': name, 'icon': icon, 'order': order, 'status': status,
                                                   'in_grid': key in ('feed', 'shorts')})
    G = apps.get_model('social', 'Gift')
    if not G.objects.exists():
        for i, (title, emoji) in enumerate([('Роза', '🌹'), ('Финики', '🌴'), ('Чай', '🍵'), ('Книга', '📖'),
                                            ('Звезда', '⭐'), ('Сердце', '💚')]):
            G.objects.create(title=title, emoji=emoji, price=0, order=i)


def backward(apps, schema_editor):
    apps.get_model('core', 'ModuleConfig').objects.filter(key__in=[m[0] for m in MODULES]).delete()


class Migration(migrations.Migration):
    dependencies = [('core', '0037_module_tracker'), ('social', '0001_initial')]
    operations = [migrations.RunPython(forward, backward)]
