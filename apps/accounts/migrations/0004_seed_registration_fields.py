"""Сидинг полей регистрации: по умолчанию спрашиваем ник и город (необязательно)."""
from django.db import migrations

FIELDS = [
    ('nickname', 'Ник', False, True, 10),
    ('city', 'Город', False, True, 20),
    ('first_name', 'Имя', False, False, 30),
]


def seed(apps, schema_editor):
    RegistrationField = apps.get_model('accounts', 'RegistrationField')
    for key, label, required, enabled, order in FIELDS:
        RegistrationField.objects.get_or_create(
            key=key,
            defaults={'label': label, 'required': required, 'enabled': enabled, 'order': order},
        )


def unseed(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0003_registrationfield_alter_user_options_user_avatar_and_more'),
    ]
    operations = [
        migrations.RunPython(seed, unseed),
    ]
