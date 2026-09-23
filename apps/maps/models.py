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
    platform_verified = models.BooleanField('проверено платформой', default=False,
                                      help_text='Ставит админ после проверки документов/контактов')

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
        ('mosque', 'Мечеть'), ('cafe', 'Кафе / ресторан'), ('shop', 'Магазин продуктов'),
        ('hotel', 'Отель'), ('butcher', 'Мясная лавка'), ('other', 'Другое'),
    ]
    category = models.CharField('категория', max_length=30, choices=CATEGORIES)

    # --- мечеть: краткая справка (заполняется, если категория «Мечеть») ---
    BRANCHES = [('sunni', 'Суннитская'), ('shia', 'Шиитская'), ('other', 'Другое')]
    MADHHABS = [
        ('hanafi', 'Ханафитский'), ('shafii', 'Шафиитский'), ('maliki', 'Маликитский'),
        ('hanbali', 'Ханбалитский'), ('jafari', 'Джафаритский'), ('mixed', 'Разные мазхабы'),
    ]
    branch = models.CharField('течение', max_length=8, choices=BRANCHES, blank=True)
    madhhab = models.CharField('мазхаб', max_length=8, choices=MADHHABS, blank=True)
    affiliation = models.CharField('кому принадлежит', max_length=200, blank=True,
                                   help_text='Например: Управление мусульман Узбекистана, округ / частная')
    imam = models.CharField('имам', max_length=120, blank=True)
    khutba_lang = models.CharField('язык хутбы', max_length=80, blank=True)
    has_jumua = models.BooleanField('джума-намаз', default=False)
    has_women = models.BooleanField('женский зал', default=False)
    has_wudu = models.BooleanField('место для омовения', default=False)
    has_parking = models.BooleanField('парковка', default=False)
    accessible = models.BooleanField('доступно для колясок', default=False)

    class Meta(BasePlace.Meta):
        verbose_name = 'халяль-место'
        verbose_name_plural = 'халяль-места'

    @property
    def is_mosque(self) -> bool:
        return self.category == 'mosque'

    def mosque_brief(self) -> str:
        """«Суннитская · ханафитский мазхаб» — для подсказки на карте."""
        parts = [self.get_branch_display()] if self.branch else []
        if self.madhhab:
            parts.append(f'{self.get_madhhab_display().lower()} мазхаб')
        return ' · '.join(parts)

    def amenities(self) -> list[str]:
        flags = [('has_jumua', 'Джума'), ('has_women', 'Женский зал'), ('has_wudu', 'Омовение'),
                 ('has_parking', 'Парковка'), ('accessible', 'Для колясок')]
        return [label for field, label in flags if getattr(self, field)]


class PlaceConfirmation(models.Model):
    """«Информация верна» — подтверждение от пользователя (одно на человека).
    Сообщение о неточности — тот же объект с is_correct=False и текстом."""

    place = models.ForeignKey(HalalPlace, on_delete=models.CASCADE, related_name='confirmations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    is_correct = models.BooleanField('информация верна', default=True)
    note = models.CharField('что неточно', max_length=500, blank=True)
    resolved = models.BooleanField('разобрано модератором', default=False)
    created_at = models.DateTimeField('когда', auto_now=True)

    class Meta:
        verbose_name = 'подтверждение / уточнение'
        verbose_name_plural = 'подтверждения и уточнения мест'
        constraints = [models.UniqueConstraint(fields=['place', 'user'], name='one_confirmation_per_user')]

    def __str__(self):
        return f'{"✓" if self.is_correct else "⚠"} {self.place} — {self.user}'
