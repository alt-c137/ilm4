from django.conf import settings
from django.db import models
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

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

    CAFES = _lazy('кафе')
    CATEGORIES = [
        ('mosque', _lazy('Мечеть')), ('cafe', _lazy('Кафе / ресторан')), ('shop', _lazy('Магазин продуктов')),
        ('hotel', _lazy('Отель')), ('butcher', _lazy('Мясная лавка')), ('other', _lazy('Другое')),
    ]
    category = models.CharField('категория', max_length=30, choices=CATEGORIES)

    # --- мечеть: краткая справка (заполняется, если категория «Мечеть») ---
    BRANCHES = [('sunni', _lazy('Суннитская')), ('shia', _lazy('Шиитская')), ('other', _lazy('Другое'))]
    MADHHABS = [
        ('hanafi', _lazy('Ханафитский')), ('shafii', _lazy('Шафиитский')), ('maliki', _lazy('Маликитский')),
        ('hanbali', _lazy('Ханбалитский')), ('jafari', _lazy('Джафаритский')), ('mixed', _lazy('Разные мазхабы')),
    ]
    MANHAJS = [
        ('sunna', _lazy('Ахлю-с-Сунна (без уточнения)')), ('ashari', _lazy('Ашариты / матуридиты')),
        ('athari', _lazy('Асариты / саляфиты')), ('sufi', _lazy('Суфийская (тарикат)')),
        ('tabligh', _lazy('Таблиг')), ('other', _lazy('Другое')),
    ]
    KINDS = [
        ('official', _lazy('Официальная (муфтият / духовное управление)')),
        ('community', _lazy('Общинная / частная')), ('foundation', _lazy('Фонд / организация')), ('other', _lazy('Другое')),
    ]
    branch = models.CharField('течение', max_length=8, choices=BRANCHES, blank=True)
    madhhab = models.CharField('мазхаб', max_length=8, choices=MADHHABS, blank=True)
    manhaj = models.CharField('манхадж / направление', max_length=8, choices=MANHAJS, blank=True,
                              help_text='Примерно, по словам прихожан. Уточняется подтверждениями')
    kind = models.CharField('на чём держится', max_length=10, choices=KINDS, blank=True)
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
            parts.append(_('{v0} мазхаб').format(v0=self.get_madhhab_display().lower()))
        return ' · '.join(parts)

    def verification(self) -> dict:
        """Насколько сведениям можно верить — одна из трёх ступеней:
        «Проверено ilm4» → «Проверили пользователи (N)» → «Не проверено»."""
        confirmed = [c for c in self.confirmations.all() if c.is_correct]
        disputed = any(not c.is_correct and not c.resolved for c in self.confirmations.all())
        names = [c.user.get_display_name() for c in confirmed[:2]]
        if self.platform_verified:
            level, label = 'ilm4', _('Проверено ilm4')
        elif confirmed:
            level, label = 'users', _('Проверили пользователи: {v1}').format(v1=len(confirmed))
        else:
            level, label = 'none', _('Не проверено')
        who = ', '.join(names) + (_(' и ещё {v1}').format(v1=len(confirmed) - len(names)) if len(confirmed) > len(names) else '')
        return {'level': level, 'label': label, 'count': len(confirmed), 'who': who, 'disputed': disputed}

    def amenities(self) -> list[str]:
        flags = [('has_jumua', _('Джума')), ('has_women', _('Женский зал')), ('has_wudu', _('Омовение')),
                 ('has_parking', _('Парковка')), ('accessible', _('Для колясок'))]
        return [label for field, label in flags if getattr(self, field)]


class PlaceConfirmation(models.Model):
    """«Информация верна» — подтверждение от пользователя (одно на человека).
    Сообщение о неточности — тот же объект с is_correct=False и текстом."""

    place = models.ForeignKey(HalalPlace, on_delete=models.CASCADE, related_name='confirmations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    is_correct = models.BooleanField('информация верна', default=True)
    note = models.CharField('что неточно', max_length=500, blank=True)
    # уточнение по полям: «на самом деле мазхаб шафиитский» — модератор применяет одной кнопкой
    suggested_branch = models.CharField('предлагают: течение', max_length=8, choices=HalalPlace.BRANCHES, blank=True)
    suggested_madhhab = models.CharField('предлагают: мазхаб', max_length=8, choices=HalalPlace.MADHHABS, blank=True)
    suggested_manhaj = models.CharField('предлагают: манхадж', max_length=8, choices=HalalPlace.MANHAJS, blank=True)
    suggested_kind = models.CharField('предлагают: на чём держится', max_length=10, choices=HalalPlace.KINDS, blank=True)
    resolved = models.BooleanField('разобрано модератором', default=False)
    created_at = models.DateTimeField('когда', auto_now=True)

    class Meta:
        verbose_name = 'подтверждение / уточнение'
        verbose_name_plural = 'подтверждения и уточнения мест'
        constraints = [models.UniqueConstraint(fields=['place', 'user'], name='one_confirmation_per_user')]

    def __str__(self):
        return f'{"✓" if self.is_correct else "⚠"} {self.place} — {self.user}'
