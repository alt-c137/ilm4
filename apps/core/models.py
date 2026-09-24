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
    hadis_details = models.TextField(
        'хадис дня — разбор (кнопка «i»)', blank=True,
        help_text='Кто передал, откуда хадис, пояснение. Показывается по кнопке «i»',
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
    # --- мессенджер: каждую функцию можно выключить (нагрузка, модерация, трафик) ---
    escrow_enabled = models.BooleanField(
        'безопасная сделка (эскроу) включена', default=False,
        help_text='Платформа удерживает деньги заказчика до сдачи работы. Удержание чужих денег '
                  'обычно требует лицензии или платёжного партнёра — включать после консультации юриста.')
    escrow_fee_percent = models.DecimalField('комиссия безопасной сделки, %', max_digits=4,
                                             decimal_places=2, default=5)
    escrow_auto_release_days = models.PositiveSmallIntegerField(
        'автопринятие работы через, дней', default=3,
        help_text='Если заказчик не принял и не открыл спор — деньги уходят исполнителю')
    feed_enabled = models.BooleanField('лента (/feed/) включена', default=True)
    chat_contacts_enabled = models.BooleanField('чат: «Найти знакомых из контактов»', default=True)
    chat_photos_enabled = models.BooleanField('чат: фото', default=True)
    chat_voice_enabled = models.BooleanField('чат: голосовые сообщения', default=True)
    chat_circles_enabled = models.BooleanField('чат: видеокружки', default=True)
    chat_calls_enabled = models.BooleanField('чат: аудиозвонки', default=True)
    chat_video_calls_enabled = models.BooleanField('чат: видеозвонки', default=True)
    webrtc_turn_url = models.CharField(
        'звонки: TURN-сервер', max_length=200, blank=True,
        help_text='Например: turn:turn.ilm4.com:3478. Без TURN часть звонков через мобильные сети не соединится')
    webrtc_turn_username = models.CharField('звонки: TURN логин', max_length=100, blank=True)
    webrtc_turn_credential = models.CharField('звонки: TURN пароль', max_length=100, blank=True)
    wallet_payouts_enabled = models.BooleanField(
        'кошелёк: вывод средств включён', default=False,
        help_text='Вывод и переводы между людьми делают кошелёк платёжным сервисом — '
                  'обычно нужна лицензия. Без вывода баланс — предоплата за услуги платформы.')
    map_maptiler_key = models.CharField(
        'карта: ключ MapTiler', max_length=80, blank=True,
        help_text='cloud.maptiler.com → API keys. В настройках ключа разрешите только свой домен. '
                  'Без ключа карта работает на запасных подложках (OpenStreetMap, Esri)')
    nikah_photo_minutes = models.PositiveSmallIntegerField(
        'никях: минут на просмотр фото', default=10,
        help_text='Сколько длится одноразовый показ фото при взаимной симпатии')
    nikah_daily_limit = models.PositiveSmallIntegerField(
        'никях: анкет в день (без премиума)', default=20,
        help_text='Сколько анкет можно просмотреть (свайпнуть) за сутки. С премиумом — без ограничения')
    nikah_premium_enabled = models.BooleanField('никях: премиум включён', default=True)
    nikah_premium_price = models.PositiveIntegerField('никях: цена премиума, сум', default=49_000)
    nikah_premium_days = models.PositiveSmallIntegerField('никях: премиум, дней', default=30)
    nikah_restore_price = models.PositiveIntegerField(
        'никях: «вернуть отклонённых», сум', default=10_000, help_text='С премиумом — бесплатно')
    nikah_ref_bonus_days = models.PositiveSmallIntegerField(
        'никях: дней премиума за приглашённого', default=3,
        help_text='Начисляется, когда анкету приглашённого одобрит модератор')
    stars_rate = models.PositiveIntegerField(
        'Telegram Stars: сум за 1 звезду', default=250,
        help_text='Пополнение через Stars: сумма в сум ÷ курс = сколько звёзд списать')
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
        'никях: цена открытия чата для брата (после взаимной симпатии), сум', default=0,
        help_text='0 — бесплатно. Сёстрам всегда бесплатно. Пока пополнение баланса не подключено — оставьте 0')
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
    duration_seconds = models.PositiveSmallIntegerField(
        'секунд показа', default=6,
        help_text='Сколько секунд слайд висит + сколько секунд заполняется линия')
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


class SocialLink(models.Model):
    """Официальные соцсети и каналы ilm4 — показываются в футере и на /support/.

    Добавил ссылку в админке — иконка появилась на сайте, без правки кода.
    """

    KINDS = [
        ('telegram', 'Telegram'), ('instagram', 'Instagram'), ('facebook', 'Facebook'),
        ('x', 'X (Twitter)'), ('youtube', 'YouTube'), ('tiktok', 'TikTok'),
        ('whatsapp', 'WhatsApp'), ('vk', 'ВКонтакте'), ('threads', 'Threads'), ('other', 'Другое'),
    ]

    kind = models.CharField('сеть', max_length=12, choices=KINDS, default='telegram')
    title = models.CharField('подпись', max_length=40, blank=True,
                             help_text='Например: «новости» — будет «Telegram · новости»')
    url = models.URLField('ссылка')
    order = models.PositiveSmallIntegerField('порядок', default=0)
    is_active = models.BooleanField('показывать', default=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'соцсеть'
        verbose_name_plural = 'соцсети и каналы'

    def __str__(self):
        return self.label

    @property
    def label(self) -> str:
        name = self.get_kind_display()
        return f'{name} · {self.title}' if self.title else name


class Report(models.Model):
    """Жалоба на публикацию, анкету или человека. Три разных жалобы — объект скрывается
    до решения модератора (как у крупных площадок: быстрее, чем ждать модерацию)."""

    REASONS = [
        ('spam', 'Спам или реклама'), ('fraud', 'Мошенничество, просят предоплату'),
        ('haram', 'Харам, неприличное содержание'), ('fake', 'Фейк, чужие фото, обман'),
        ('contacts', 'Контакты в анкете / уводят в другие мессенджеры'),
        ('abuse', 'Оскорбления, угрозы'), ('other', 'Другое'),
    ]
    NEW, RESOLVED, DISMISSED = 'new', 'resolved', 'dismissed'
    STATUSES = [(NEW, 'новая'), (RESOLVED, 'меры приняты'), (DISMISSED, 'отклонена')]

    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports_sent')
    reason = models.CharField('причина', max_length=10, choices=REASONS)
    text = models.CharField('подробности', max_length=500, blank=True)
    status = models.CharField('статус', max_length=10, choices=STATUSES, default=NEW, db_index=True)
    created_at = models.DateTimeField('когда', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'жалоба'
        verbose_name_plural = 'жалобы'
        constraints = [models.UniqueConstraint(fields=['content_type', 'object_id', 'reporter'],
                                               name='one_report_per_user')]

    def __str__(self):
        return f'{self.get_reason_display()} — {self.content_type.model}#{self.object_id}'

    @property
    def target(self):
        return self.content_type.get_object_for_this_type(pk=self.object_id)
