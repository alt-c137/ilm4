from django.conf import settings
from django.db import models

from apps.core.models import Moderation


class Book(models.Model):
    """Книга библиотеки: разделы, бесплатная (price=0) или платная."""

    CATEGORIES = [
        ('akida', 'Акыда'), ('fiqh', 'Фикх'), ('quran', 'Коран и таджвид'),
        ('arabic', 'Арабский язык'), ('history', 'История Ислама'),
        ('family', 'Семья и воспитание'), ('other', 'Другое'),
    ]

    title = models.CharField('название', max_length=200)
    category = models.CharField('раздел', max_length=20, choices=CATEGORIES,
                                default='other')
    author = models.CharField('автор', max_length=160, blank=True)
    description = models.TextField('описание', blank=True)
    cover = models.ImageField('обложка', upload_to='books/%Y/%m/', blank=True, null=True)
    file = models.FileField('файл книги', upload_to='books/files/%Y/%m/',
                            help_text='PDF/EPUB до 50 МБ')
    price = models.DecimalField('цена, сум (0 — бесплатно)', max_digits=10,
                                decimal_places=0, default=0)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                              related_name='books')
    status = models.CharField('статус', max_length=10, choices=Moderation.CHOICES,
                              default=Moderation.PENDING)
    created_at = models.DateTimeField('добавлено', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'книга'
        verbose_name_plural = 'библиотека'

    def __str__(self):
        return self.title


class BookPurchase(models.Model):
    """Покупка платной книги: одна на пользователя (повторно — бесплатно)."""

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='purchases')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='book_purchases')
    created_at = models.DateTimeField('куплено', auto_now_add=True)

    class Meta:
        unique_together = ('book', 'user')
        verbose_name = 'покупка книги'
        verbose_name_plural = 'покупки книг'
