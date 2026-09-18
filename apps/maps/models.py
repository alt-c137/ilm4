from django.conf import settings
from django.db import models

from apps.core.models import Moderation


class BasePlace(models.Model):
    """Общий слой геообъектов (ARCHITECTURE.md §2 «Карта»).

    Координаты — широта/долгота (PostGIS подключается на проде без изменения UI:
    «рядом со мной» считается гаверсинусом, точности витрины достаточно).
    """

    name = models.CharField('название', max_length=160)
    category = models.CharField('категория', max_length=30)
    city = models.CharField('город', max_length=80)
    address = models.CharField('адрес', max_length=240, blank=True)
    lat = models.DecimalField('широта', max_digits=9, decimal_places=6)
    lon = models.DecimalField('долгота', max_digits=9, decimal_places=6)
    phone = models.CharField('телефон', max_length=60, blank=True)
    url = models.URLField('сайт/соцсеть', blank=True)
    description = models.TextField('описание', blank=True)
    photo = models.ImageField('фото', upload_to='places/', blank=True, null=True)
    status = models.CharField('статус', max_length=10, choices=Moderation.CHOICES,
                              default=Moderation.PENDING)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='%(class)ss',
                              verbose_name='кто добавил')
    created_at = models.DateTimeField('добавлено', auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    @property
    def is_approved(self) -> bool:
        return self.status == Moderation.APPROVED

    def __str__(self):
        return f'{self.name} ({self.city})'


class HalalPlace(BasePlace):
    """Халяль-место: кафе, ресторан, магазин, отель."""

    CAFES = 'кафе'
    CATEGORIES = [
        ('cafe', 'Кафе / ресторан'), ('shop', 'Магазин продуктов'),
        ('hotel', 'Отель'), ('butcher', 'Мясная лавка'), ('other', 'Другое'),
    ]
    category = models.CharField('категория', max_length=30, choices=CATEGORIES)

    class Meta(BasePlace.Meta):
        verbose_name = 'халяль-место'
        verbose_name_plural = 'халяль-места'
