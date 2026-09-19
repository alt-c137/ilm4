from django.conf import settings
from django.db import models
from solo.models import SingletonModel


class Moderation:
    """Общий статус модерации контента (объявления, места, врачи, анкеты, темы)."""

    PENDING, APPROVED, REJECTED = 'pending', 'approved', 'rejected'
    CHOICES = [(PENDING, 'На модерации'), (APPROVED, 'Опубликован'), (REJECTED, 'Отклонён')]


class Theme(models.Model):
    """Палитра оформления «Апп»: три акцента перекрашивают весь сайт (§3.3).

    Набор — из дизайн-макета ilm4-design-C-app.html (переключатель внизу справа).
    """

    name = models.CharField('название', max_length=50)
    accent = models.CharField('акцент', max_length=9)
    accent_d = models.CharField('акцент тёмный', max_length=9)
    accent_soft = models.CharField('акцент мягкий', max_length=9)
    is_dark = models.BooleanField('тёмная тема', default=False)  # задел на будущее
    order = models.PositiveSmallIntegerField('порядок', default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'тема оформления'
        verbose_name_plural = 'темы оформления'

    def __str__(self):
        return self.name


class ModuleConfig(models.Model):
    """Раздел платформы и его статус: вкл / выкл / скоро (§3.1).

    Раздел без записи здесь считается выключенным (404). Статус «скоро»
    показывает витрину-заглушку с плашкой «Скоро».
    """

    ON, OFF, SOON = 'on', 'off', 'soon'
    STATUS = [(ON, 'включён'), (OFF, 'выключен'), (SOON, 'скоро')]

    key = models.CharField('ключ (имя раздела)', max_length=30, unique=True)
    name = models.CharField('название', max_length=80)
    status = models.CharField('статус', max_length=4, choices=STATUS, default=SOON)
    order = models.PositiveSmallIntegerField('порядок', default=0)
    icon = models.CharField('иконка', max_length=8, default='✦',
                            help_text='Эмодзи-фоллбек: если в static/img/icons/ есть '
                                      '<ключ>.svg или .png — показывается он')
    in_grid = models.BooleanField('показывать на главной', default=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'раздел'
        verbose_name_plural = 'разделы'

    def __str__(self):
        return self.name


class SiteSettings(SingletonModel):
    """Настройки сайта из админки (§3.4). Пополняется по фазам."""

    site_name = models.CharField('название сайта', max_length=50, default='ilm4')
    default_theme = models.ForeignKey(
        Theme, verbose_name='тема по умолчанию', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    hadis_enabled = models.BooleanField('хадис дня включён', default=True)
    hadis_text = models.TextField(
        'хадис дня — текст',
        default='«Поистине, дела оцениваются по намерениям».',
    )
    hadis_source = models.CharField(
        'хадис дня — источник', max_length=200, default='аль-Бухари, Муслим',
    )
    hadis_image = models.ImageField(
        'хадис — фоновая картинка', upload_to='settings/', blank=True, null=True,
        help_text='Фон карточки хадиса на главной; без неё — фирменный градиент',
    )
    hero_image = models.ImageField(
        'герой — картинка справа', upload_to='settings/', blank=True, null=True,
        help_text='Иллюстрация в правой части главного баннера',
    )
    news_ticker = models.BooleanField('бегущая строка новостей', default=False)
    min_payout = models.PositiveIntegerField('минимальная сумма вывода, сум', default=100_000)
    prayer_method = models.CharField(
        'метод расчёта намаза', max_length=10, default='Karachi',
        help_text='Karachi (СНГ/Азия), MWL, ISNA, Makkah, Egypt',
    )
    doctor_publish_price = models.PositiveIntegerField(
        'цена публикации врача, сум (0 — бесплатно)', default=0,
    )
    market_moderation = models.BooleanField(
        'модерация объявлений ilmbuy', default=True,
        help_text='Выключи, если объявлений слишком много для ручной проверки',
    )
    boost_price = models.PositiveIntegerField('цена буста объявления (7 дней), сум',
                                              default=20_000)
    nikah_chat_price = models.PositiveIntegerField(
        'никах: цена «написать» для мужчин, сум', default=10_000)
    nikah_boost_price = models.PositiveIntegerField(
        'никах: цена буста анкеты (7 дней), сум', default=15_000)
    support_text = models.TextField(
        'текст «Поддержать проект»',
        default='ilm4 живёт на пожертвования уммы — садака джария, '
                'пока люди получают знания и пользу.',
    )

    class Meta:
        verbose_name = 'настройки сайта'

    def __str__(self):
        return 'Настройки сайта'


class Banner(models.Model):
    """Слайд рекламной карусели на главной. Управляется из админки.

    Если активных слайдов нет — карусель показывает три фирменных
    слайда-приглашения (как сейчас).
    """

    image = models.ImageField('картинка 1600×500', upload_to='banners/')
    title = models.CharField('заголовок', max_length=120)
    subtitle = models.CharField('подпись', max_length=200, blank=True)
    cta_text = models.CharField('надпись кнопки', max_length=40, default='Подробнее')
    cta_url = models.CharField('ссылка кнопки', max_length=300, default='/')
    order = models.PositiveSmallIntegerField('порядок', default=0)
    is_active = models.BooleanField('активен', default=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'баннер'
        verbose_name_plural = 'баннеры (реклама на главной)'

    def __str__(self):
        return self.title


class Rate(models.Model):
    """Курс валют к суму. Обновляется командой python manage.py pull_rates."""

    code = models.CharField('код валюты', max_length=6, unique=True)
    rate = models.DecimalField('курс к суму', max_digits=14, decimal_places=2)
    updated = models.DateTimeField('обновлено', auto_now=True)

    class Meta:
        ordering = ['code']
        verbose_name = 'курс валюты'
        verbose_name_plural = 'курсы валют'

    def __str__(self):
        return f'{self.code}: {self.rate}'


class Notification(models.Model):
    """Уведомление пользователю (колокольчик). Каркас; живая доставка — фаза 8."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='notifications', verbose_name='пользователь')
    text = models.TextField('текст')
    url = models.CharField('ссылка', max_length=500, blank=True)
    read = models.BooleanField('прочитано', default=False)
    created_at = models.DateTimeField('создано', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'уведомление'
        verbose_name_plural = 'уведомления'

    def __str__(self):
        return self.text[:60]
