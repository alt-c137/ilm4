"""Аналитика использования: сколько времени и как часто люди бывают в каждом разделе.

Храним не каждое действие, а одну строку на «человек × день × раздел × сайт/приложение»: число открытий и секунды.
Этого хватает, чтобы понять: какие разделы живые, какие лишние, как часто возвращаются (день 1 / 7 / 30).
Что человек лайкает, сохраняет и репостит — уже есть в apps/social; по этому строится порядок ленты.
"""
from django.conf import settings
from django.db import models


class Use(models.Model):
    WEB, APP = 'web', 'app'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name='uses')
    anon = models.CharField('гость (случайный номер из куки)', max_length=16, blank=True)
    day = models.DateField(db_index=True)
    section = models.CharField(max_length=24, db_index=True)
    platform = models.CharField(max_length=3, default=WEB)
    opens = models.PositiveIntegerField(default=0)
    seconds = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'anon', 'day', 'section', 'platform'], name='one_use_row')]
        indexes = [models.Index(fields=['day', 'section'])]
        verbose_name = 'использование раздела за день'
        verbose_name_plural = 'использование разделов'
