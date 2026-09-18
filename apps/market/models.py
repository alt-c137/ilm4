
from django.conf import settings
from django.db import models
from django.utils import timezone
from taggit.managers import TaggableManager

from apps.core.models import Moderation


class Category(models.Model):
    """Категория объявлений (Авто — тоже категория, PASSPORT §2)."""

    name = models.CharField('название', max_length=60, unique=True)
    slug = models.SlugField('слаг', unique=True)
    order = models.PositiveSmallIntegerField('порядок', default=0)
    icon = models.CharField('иконка', max_length=8, default='📦')

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'категория'
        verbose_name_plural = 'категории'

    def __str__(self):
        return self.name


class Listing(models.Model):
    """Объявление ilmbuy."""

    CURRENCIES = [('UZS', 'сум'), ('USD', '$'), ('RUB', '₽')]

    title = models.CharField('заголовок', max_length=140)
    description = models.TextField('описание')
    price = models.DecimalField('цена', max_digits=14, decimal_places=0, default=0)
    currency = models.CharField('валюта', max_length=3, choices=CURRENCIES, default='UZS')
    category = models.ForeignKey(Category, on_delete=models.PROTECT,
                                 related_name='listings', verbose_name='категория')
    city = models.CharField('город', max_length=80)
    contact = models.CharField('контакт (телефон/ник)', max_length=100, blank=True,
                               help_text='Пусто — покажем email из профиля')
    photo = models.ImageField('фото', upload_to='listings/%Y/%m/', blank=True, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='listings', verbose_name='автор')
    status = models.CharField('статус', max_length=10, choices=Moderation.CHOICES,
                              default=Moderation.PENDING)
    is_active = models.BooleanField('активно', default=True)  # автор снял с продажи
    boosted_until = models.DateTimeField('буст до', null=True, blank=True)
    views = models.PositiveIntegerField('просмотры', default=0)
    created_at = models.DateTimeField('создано', auto_now_add=True, db_index=True)
    tags = TaggableManager(blank=True)

    class Meta:
        ordering = ['-boosted_until', '-created_at']  # буст наверх
        verbose_name = 'объявление'
        verbose_name_plural = 'объявления'

    def __str__(self):
        return f'{self.title} — {self.price} {self.get_currency_display()}'

    @property
    def is_boosted(self) -> bool:
        return self.boosted_until and self.boosted_until > timezone.now()

    @property
    def is_approved(self) -> bool:
        return self.status == Moderation.APPROVED

    @property
    def price_display(self) -> str:
        return 'Даром' if self.price == 0 else str(self.price)

    @property
    def visible(self) -> bool:
        return self.is_active and self.status == Moderation.APPROVED
