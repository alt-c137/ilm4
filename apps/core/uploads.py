"""Проверка картинок, которые загружают пользователи.

Файл обязан быть настоящим изображением (Pillow) с расширением картинки —
иначе под видом «фото» можно положить HTML/SVG и выполнить скрипт с нашего домена.
"""
from django import forms
from django.core.exceptions import ValidationError

MAX_IMAGE_MB = 10


def clean_image(upload, max_mb: int = MAX_IMAGE_MB):
    """Вернуть проверенный файл или None (пусто); ошибка — ValidationError с текстом."""
    if not upload:
        return None
    if upload.size > max_mb * 1024 * 1024:
        raise ValidationError(f'Фото больше {max_mb} МБ')
    field = forms.ImageField()   # Pillow + разрешённые расширения (jpg, png, webp…)
    upload = field.clean(upload)
    for validator in field.default_validators:
        validator(upload)
    return upload
