from django.conf import settings
from django.db import models

from apps.core.models import Moderation


class Story(models.Model):
    """История переезда: из какой страны в какую, опыт, решения проблем."""

    title = models.CharField('заголовок', max_length=200)
    country_from = models.CharField('откуда', max_length=60)
    country_to = models.CharField('куда', max_length=60)
    body = models.TextField('история')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='migration_stories')
    status = models.CharField('статус', max_length=10, choices=Moderation.CHOICES,
                              default=Moderation.PENDING)
    created_at = models.DateTimeField('создано', auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'история переезда'
        verbose_name_plural = 'истории переездов'

    def __str__(self):
        return f'{self.title} ({self.country_from} → {self.country_to})'
