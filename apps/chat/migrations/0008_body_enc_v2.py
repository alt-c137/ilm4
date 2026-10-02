"""Текст сообщения: поле `body` (Fernet-поле) → `body_enc` в той же колонке `body`.

Колонка в базе не меняется (тот же текст), меняется только то, как с ней работает код:
шифрование теперь делает модель с ключом своего чата (keyring.py). Старые значения
`enc1:` читаются как раньше; перевод на новый формат — `manage.py chat_keys migrate`.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0007_witness'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name='message', name='body'),
                migrations.AddField(
                    model_name='message', name='body_enc',
                    field=models.TextField(blank=True, db_column='body', verbose_name='текст (зашифрован)'),
                ),
            ],
            database_operations=[],
        ),
    ]
