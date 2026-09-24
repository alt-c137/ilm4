from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _lazy

from apps.core.models import Moderation


class Ride(models.Model):
    """Перевозка: груз, пассажиры или оба. Публикуется после модерации."""

    TYPES = [
        ('cargo', _lazy('Грузоперевозка')),
        ('pax', _lazy('Пассажирская перевозка')),
        ('both', _lazy('Груз и пассажиры')),
    ]

    from_city = models.CharField('откуда', max_length=80, db_index=True)
    to_city = models.CharField('куда', max_length=80, db_index=True)
    type = models.CharField('тип', max_length=6, choices=TYPES, default='cargo')
    company = models.CharField('перевозчик / компания', max_length=120, blank=True,
                               help_text='Название компании или имя перевозчика')
    ride_date = models.DateField('дата поездки', null=True, blank=True,
                                 help_text='Если поездка разовая')
    price_text = models.CharField('цена (текстом)', max_length=120, blank=True)
    description = models.TextField('описание',
                                   help_text='Что везёте, машина, вместимость, периодичность')
    contact = models.CharField('контакт', max_length=120)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='rides')
    status = models.CharField('статус', max_length=10, choices=Moderation.CHOICES,
                              default=Moderation.PENDING)
    created_at = models.DateTimeField('создано', auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['from_city', 'to_city'])]
        verbose_name = 'перевозка'
        verbose_name_plural = 'перевозки'

    def __str__(self):
        return f'{self.from_city} → {self.to_city} ({self.get_type_display()})'
