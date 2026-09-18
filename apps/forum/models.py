from django.conf import settings
from django.db import models

from apps.core.models import Moderation


class Topic(models.Model):
    """Тема форума «вопрос-ответ». Тема проходит модерацию (PASSPORT §3)."""

    title = models.CharField('вопрос', max_length=200)
    body = models.TextField('подробности', blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='topics')
    status = models.CharField('статус', max_length=10, choices=Moderation.CHOICES,
                              default=Moderation.PENDING)
    created_at = models.DateTimeField('создано', auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'тема'
        verbose_name_plural = 'темы форума'

    def __str__(self):
        return self.title


class Reply(models.Model):
    """Ответ в теме. Ответы модерации не проходят (тема уже одобрена),
    модератор удаляет при жалобах."""

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='replies')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='replies')
    body = models.TextField('ответ')
    created_at = models.DateTimeField('создано', auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'ответ'
        verbose_name_plural = 'ответы'

    def __str__(self):
        return f'{self.author}: {self.body[:40]}'
