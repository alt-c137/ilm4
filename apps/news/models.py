from django.conf import settings
from django.db import models


class NewsPost(models.Model):
    """Новость. Публикуют только админы (через админку) — модерация не нужна."""

    title = models.CharField('заголовок', max_length=200)
    slug = models.SlugField('слаг', unique=True)
    summary = models.CharField('кратко', max_length=300, blank=True)
    body = models.TextField('текст')
    cover = models.ImageField('обложка', upload_to='news/%Y/%m/', blank=True, null=True)
    is_pinned = models.BooleanField('закреплена', default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name='news_posts', verbose_name='автор')
    created_at = models.DateTimeField('создано', auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = 'новость'
        verbose_name_plural = 'новости'

    def __str__(self):
        return self.title
