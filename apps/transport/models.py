from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _lazy

from apps.core import money
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


class Trip(models.Model):
    """Попутчики: «еду из Медины в Мекку, есть два места» или «ищу машину до Ташкента».

    Не перевозчик-компания (это Ride), а обычный человек со своей поездкой: дата и время,
    машина, сколько мест, цена за место, кого берёт. Места занимаются заявкой (TripRequest):
    водитель подтверждает — свободных мест становится меньше.
    """

    DRIVER, PASSENGER = 'driver', 'passenger'
    ROLES = [(DRIVER, _lazy('Еду на машине — возьму попутчиков')), (PASSENGER, _lazy('Ищу машину'))]
    AUDIENCE = [('any', _lazy('Любые попутчики')), ('men', _lazy('Только братья')), ('women', _lazy('Только сёстры')),
                ('family', _lazy('Семьи и сёстры с махрамом'))]

    role = models.CharField('кто вы', max_length=10, choices=ROLES, default=DRIVER)
    from_city = models.CharField('откуда', max_length=80, db_index=True)
    to_city = models.CharField('куда', max_length=80, db_index=True)
    via = models.CharField('по пути (через какие города)', max_length=200, blank=True,
                           help_text='Через запятую — этих людей тоже можно подобрать по дороге')
    departs_at = models.DateTimeField('выезд', db_index=True)
    # Время выезда — местное для города выезда (как в билете): храним точный момент и смещение пояса
    # автора. Иначе «14:30» из Медины для сервера в другом поясе уехало бы на два часа раньше.
    tz_offset = models.SmallIntegerField('часовой пояс выезда (минут от UTC)', null=True, blank=True)
    car = models.CharField('машина', max_length=80, blank=True, help_text='Марка и цвет: «Toyota Camry, белая»')
    seats = models.PositiveSmallIntegerField('мест', default=1,
                                             help_text='Водителю — сколько свободных мест; пассажиру — сколько вас')
    front_seat = models.BooleanField('переднее место свободно', default=False)
    price = models.DecimalField('цена за место', max_digits=12, decimal_places=0, default=0,
                                help_text='0 — бесплатно, ради Аллаха')
    currency = models.CharField('валюта', max_length=3, choices=money.CHOICES, default='USD')
    audience = models.CharField('кого беру', max_length=8, choices=AUDIENCE, default='any')
    parcels = models.BooleanField('возьму посылку', default=False)
    comment = models.TextField('комментарий', blank=True, max_length=1000,
                               help_text='Место встречи, багаж, остановки на намаз')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trips')
    status = models.CharField('статус', max_length=10, choices=Moderation.CHOICES, default=Moderation.PENDING)
    is_active = models.BooleanField('показывать', default=True)
    created_at = models.DateTimeField('создано', auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['departs_at']
        indexes = [models.Index(fields=['from_city', 'to_city', 'departs_at'])]
        verbose_name = 'поездка (попутчики)'
        verbose_name_plural = 'попутчики'

    def __str__(self):
        return f'{self.from_city} → {self.to_city}, {self.departs_local:%d.%m %H:%M}'

    @property
    def is_driver(self) -> bool:
        return self.role == self.DRIVER

    @property
    def departs_local(self):
        """Время выезда «как на часах» в городе выезда — его и показываем всем."""
        from datetime import timedelta
        from datetime import timezone as dt_tz

        from django.utils import timezone
        if self.tz_offset is None:
            return timezone.make_naive(self.departs_at)
        return self.departs_at.astimezone(dt_tz(timedelta(minutes=self.tz_offset))).replace(tzinfo=None)

    @property
    def taken(self) -> int:
        """Сколько мест уже подтверждено."""
        if not self.pk:
            return 0
        cached = getattr(self, '_taken', None)
        if cached is None:
            cached = self.requests.filter(status=TripRequest.ACCEPTED).aggregate(n=models.Sum('seats'))['n'] or 0
            self._taken = cached
        return cached

    @property
    def seats_left(self) -> int:
        return max(0, self.seats - self.taken) if self.is_driver else self.seats

    @property
    def is_past(self) -> bool:
        from django.utils import timezone
        return self.departs_at < timezone.now()


class TripRequest(models.Model):
    """Заявка на место: попутчик просит — водитель подтверждает или отказывает."""

    PENDING, ACCEPTED, DECLINED, CANCELLED = 'pending', 'accepted', 'declined', 'cancelled'
    STATUSES = [(PENDING, _lazy('Ждёт ответа')), (ACCEPTED, _lazy('Подтверждено')), (DECLINED, _lazy('Отказ')),
                (CANCELLED, _lazy('Отменена'))]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='requests')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trip_requests')
    seats = models.PositiveSmallIntegerField('мест', default=1)
    status = models.CharField('статус', max_length=10, choices=STATUSES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        constraints = [models.UniqueConstraint(fields=['trip', 'user'], name='one_request_per_trip')]
        verbose_name = 'заявка на место'
        verbose_name_plural = 'заявки на места'

    def __str__(self):
        return f'{self.user} → {self.trip} ({self.seats})'
