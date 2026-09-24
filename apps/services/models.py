from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _lazy

from apps.core.models import Moderation


class Service(models.Model):
    """Услуга: нотариальные переводы, исламские юристы, туры (хадж/умра), прочее."""

    KINDS = [
        ('translate', _lazy('Переводы документов (нотариальные)')),
        ('lawyer', _lazy('Исламский юрист / консультация')),
        ('freelance', _lazy('Фриланс: удалённая работа')),
        ('tour', _lazy('Туры: хадж и умра')),
        ('other', _lazy('Другая услуга')),
    ]

    name = models.CharField('название', max_length=160)
    kind = models.CharField('вид', max_length=12, choices=KINDS)
    city = models.CharField('город', max_length=80, blank=True)
    description = models.TextField('описание')
    price_text = models.CharField('цена (текстом)', max_length=120, blank=True)
    contact = models.CharField('контакт', max_length=120)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='services')
    status = models.CharField('статус', max_length=10, choices=Moderation.CHOICES,
                              default=Moderation.PENDING)
    created_at = models.DateTimeField('создано', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'услуга'
        verbose_name_plural = 'услуги'

    def __str__(self):
        return f'{self.name} ({self.get_kind_display()})'
