"""Отзывы и рейтинги — один механизм для всего, что можно оценить.

Цель отзыва — любой объект из REVIEWABLE (продавец/исполнитель = пользователь,
халяль-место, врач). Новый тип добавляется одной строкой в REVIEWABLE, без
миграций. Один отзыв от человека на объект (повторная отправка — правка).
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# что можно оценивать: 'app_label.model'
REVIEWABLE = {'accounts.user', 'maps.halalplace', 'health.doctor'}


class Review(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name='тип объекта')
    object_id = models.PositiveBigIntegerField('id объекта', db_index=True)
    target = GenericForeignKey('content_type', 'object_id')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='reviews_written', verbose_name='автор')
    # пусто — сообщение без оценки (например, о мечети: звёзды там неуместны)
    rating = models.PositiveSmallIntegerField('оценка', null=True, blank=True,
                                              validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField('текст', max_length=2000, blank=True)
    reply = models.TextField('ответ владельца', max_length=2000, blank=True)
    replied_at = models.DateTimeField('ответ дан', null=True, blank=True)
    is_hidden = models.BooleanField('скрыт модератором', default=False)
    created_at = models.DateTimeField('создан', auto_now_add=True)
    updated_at = models.DateTimeField('изменён', auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'отзыв'
        verbose_name_plural = 'отзывы'
        constraints = [models.UniqueConstraint(fields=['content_type', 'object_id', 'author'],
                                               name='one_review_per_author')]
        indexes = [models.Index(fields=['content_type', 'object_id', 'is_hidden'])]

    def __str__(self):
        return f'{self.rating or "—"}★ от {self.author} → {self.content_type.model}#{self.object_id}'
