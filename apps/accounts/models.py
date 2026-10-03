from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _lazy


class User(AbstractUser):
    """Единый пользователь платформы (PASSPORT §7.2).

    Вход — по email (или имени). Роли: участник / поддержка / админ /
    супер-админ. Супер-админов двое (владельцы): это is_superuser=True,
    свойство is_super_admin учитывает оба признака.
    """

    ROLE_USER = 'user'
    ROLE_SUPPORT = 'support'
    ROLE_ADMIN = 'admin'
    ROLE_SUPER = 'super_admin'
    ROLES = [
        (ROLE_USER, _lazy('Участник')),
        (ROLE_SUPPORT, _lazy('Поддержка')),
        (ROLE_ADMIN, _lazy('Админ')),
        (ROLE_SUPER, _lazy('Супер-админ')),
    ]

    email = models.EmailField('email', unique=True)
    nickname = models.CharField('ник', max_length=40, blank=True)
    city = models.CharField('город', max_length=80, blank=True)
    avatar = models.ImageField('аватар', upload_to='avatars/', blank=True, null=True)
    role = models.CharField('роль', max_length=12, choices=ROLES, default=ROLE_USER)
    phone = models.CharField('телефон', max_length=20, blank=True)
    phone_key = models.CharField('ключ номера (хеш последних 9 цифр)', max_length=64, blank=True,
                                 db_index=True, editable=False)
    phone_verified_at = models.DateTimeField(
        'номер подтверждён', null=True, blank=True,
        help_text='Когда номер подтверждён через Telegram (кнопка «Отправить мой номер»). '
                  'Один номер — один аккаунт: так боты не плодят объявления и анкеты')
    findable_by_phone = models.BooleanField(
        'меня можно найти по номеру', default=True,
        help_text='Кто знает ваш номер, найдёт вас в поиске чатов. Сам номер при этом не показывается')
    # --- профиль и приватность «как в Telegram» (people.py) ---
    ALL, CLOSE, NOBODY = 'all', 'close', 'nobody'
    PRIVACY = [(ALL, _lazy('Все')), (CLOSE, _lazy('Близкие друзья')), (NOBODY, _lazy('Никто'))]
    handle = models.CharField('имя пользователя (@имя)', max_length=32, blank=True, null=True, unique=True,
                              help_text='По нему вас находят в поиске. Латинские буквы, цифры и «_»')
    bio = models.CharField('о себе', max_length=160, blank=True)
    last_seen_at = models.DateTimeField('был(а) в сети', null=True, blank=True, editable=False)
    phone_privacy = models.CharField('кто видит мой номер', max_length=6, choices=PRIVACY, default=NOBODY)
    seen_privacy = models.CharField('кто видит, когда я в сети', max_length=6, choices=PRIVACY, default=ALL)
    forward_privacy = models.CharField('кто может ссылаться на мой профиль при пересылке', max_length=6,
                                       choices=PRIVACY, default=ALL)
    invite_privacy = models.CharField('кто может добавлять меня в группы', max_length=6, choices=PRIVACY, default=ALL)
    counts_privacy = models.CharField('кто видит мои счётчики (записи, подписчики, подписки)', max_length=6, choices=PRIVACY, default=ALL)
    birthday = models.DateField('день рождения', null=True, blank=True)
    # свои настройки интерфейса: какие кнопки внизу экрана (сайт и приложение — отдельно)
    ui = models.JSONField('настройки интерфейса', default=dict, blank=True)
    telegram_id = models.BigIntegerField('Telegram ID', null=True, blank=True, unique=True,
                                         help_text='Заполняется при входе из Telegram (мини-приложение)')
    telegram_username = models.CharField('Telegram @', max_length=64, blank=True)
    currency = models.CharField('валюта для цен', max_length=3, blank=True,
                                help_text='В ней показываем «≈» рядом с ценами. Пусто — определяем сами: по стране или номеру')
    language = models.CharField('язык интерфейса', max_length=8, blank=True,
                                help_text='Уведомления и сообщения бота приходят на этом языке')
    platform_verified = models.BooleanField(
        'проверен платформой', default=False,
        help_text='Продавец/исполнитель/заведение проверены админом (документы, контакты)')
    theme = models.ForeignKey(
        'core.Theme', verbose_name='тема оформления', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        verbose_name = 'пользователь'
        verbose_name_plural = 'пользователи'

    # --- роли (проверки в view — PASSPORT §3, не только скрытие ссылок) ---
    @property
    def is_super_admin(self) -> bool:
        return self.is_superuser or self.role == self.ROLE_SUPER

    @property
    def is_admin_role(self) -> bool:
        return self.is_superuser or self.role in (self.ROLE_ADMIN, self.ROLE_SUPER)

    @property
    def is_support_role(self) -> bool:
        return self.is_superuser or self.role in (self.ROLE_SUPPORT, self.ROLE_ADMIN, self.ROLE_SUPER)

    def save(self, *args, **kwargs):
        from .phones import phone_key
        self.phone_key = phone_key(self.phone) if self.phone else ''
        super().save(*args, **kwargs)

    @property
    def phone_verified(self) -> bool:
        return self.phone_verified_at is not None

    def get_display_name(self) -> str:
        # как в Telegram: имя и фамилия; старый «ник» — только если имени нет
        return f'{self.first_name} {self.last_name}'.strip() or self.nickname or self.username

    def __str__(self):
        return f'{self.get_display_name()} ({self.email})'


class SocialLink(models.Model):
    """Ссылка на соцсеть в профиле: Instagram, Telegram, YouTube… У каждой — кто её видит."""

    KINDS = [('telegram', 'Telegram'), ('instagram', 'Instagram'), ('youtube', 'YouTube'), ('tiktok', 'TikTok'),
             ('whatsapp', 'WhatsApp'), ('facebook', 'Facebook'), ('x', 'X (Twitter)'), ('vk', 'VK'),
             ('github', 'GitHub'), ('discord', 'Discord'), ('linkedin', 'LinkedIn'), ('website', _lazy('Сайт')),
             ('other', _lazy('Другое'))]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='social_links')
    kind = models.CharField('сеть', max_length=12, choices=KINDS)
    value = models.CharField('имя или ссылка', max_length=120)
    privacy = models.CharField('кто видит', max_length=6, choices=User.PRIVACY, default=User.ALL)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'ссылка на соцсеть'
        verbose_name_plural = 'ссылки на соцсети'

    def __str__(self):
        return f'{self.get_kind_display()}: {self.value}'


class ProfilePhoto(models.Model):
    """Фото профиля — как в Telegram, их может быть несколько: новое становится главным, старые листаются."""

    MAX = 30

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField('фото', upload_to='avatars/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = 'фото профиля'
        verbose_name_plural = 'фото профиля'


class Contact(models.Model):
    """Контакт — как в Telegram: человек, которого я сохранил себе (по номеру или из профиля), под своим именем."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contacts')
    friend = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contact_of')
    first_name = models.CharField('имя (как записал я)', max_length=60, blank=True)
    last_name = models.CharField('фамилия', max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'friend'], name='one_contact')]
        verbose_name = 'контакт'
        verbose_name_plural = 'контакты'

    @property
    def name(self) -> str:
        return ' '.join(x for x in (self.first_name, self.last_name) if x) or self.friend.get_display_name()


class DeviceAccount(models.Model):
    """«Запомненный вход» для переключения аккаунтов на одном устройстве (apps/accounts/multi.py). Ключ хранится хешем."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_accounts')
    token_hash = models.CharField(max_length=64, unique=True)
    auth_hash = models.CharField(max_length=128)          # сменили пароль — запись больше не подходит
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'запомненный вход (несколько аккаунтов)'
        verbose_name_plural = 'запомненные входы (несколько аккаунтов)'


class CloseFriend(models.Model):
    """«Близкие друзья»: кому человек показывает то, что скрыто от остальных (номер, соцсети, время в сети)."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='close_friends')
    friend = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='close_of')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'friend'], name='one_close_friend')]
        verbose_name = 'близкий друг'
        verbose_name_plural = 'близкие друзья'


class RegistrationField(models.Model):
    """Гибкая регистрация: какие поля спрашивать — решает админ (PASSPORT §2).

    key жёстко соответствует полям формы регистрации; email и пароль
    спрашиваются всегда.
    """

    KEYS = [
        ('nickname', _lazy('Ник')),
        ('city', _lazy('Город')),
        ('first_name', _lazy('Имя')),
    ]
    key = models.CharField('поле', max_length=20, choices=KEYS, unique=True)
    label = models.CharField('подпись', max_length=60)
    required = models.BooleanField('обязательное', default=False)
    enabled = models.BooleanField('спрашивать при регистрации', default=True)
    order = models.PositiveSmallIntegerField('порядок', default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'поле регистрации'
        verbose_name_plural = 'поля регистрации'

    def __str__(self):
        return self.label


class AuditLog(models.Model):
    """Журнал действий: входы админов, изменения ролей, модерация (PASSPORT §3).

    Записи только добавляются; в админке — только чтение.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='кто', null=True,
        on_delete=models.SET_NULL, related_name='audit_logs',
    )
    action = models.CharField('действие', max_length=120)
    target = models.CharField('объект', max_length=200, blank=True)
    ip = models.GenericIPAddressField('IP', null=True, blank=True)
    created_at = models.DateTimeField('когда', auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'запись журнала'
        verbose_name_plural = 'журнал действий'

    def __str__(self):
        return f'{self.user or "система"}: {self.action}'


class UserBlock(models.Model):
    """Блокировка: заблокированный не может писать и не видит вас в никяхе (и наоборот)."""

    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blocks_made')
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blocked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')
        verbose_name = 'блокировка'
        verbose_name_plural = 'блокировки'

    @staticmethod
    def between(a, b) -> bool:
        """Есть ли блокировка в любую сторону."""
        if not (a and b and getattr(a, 'pk', None) and getattr(b, 'pk', None)):
            return False
        return UserBlock.objects.filter(models.Q(blocker=a, blocked=b) | models.Q(blocker=b, blocked=a)).exists()

    @staticmethod
    def ids_for(user) -> set:
        """id всех, с кем у пользователя блокировка (в любую сторону)."""
        pairs = UserBlock.objects.filter(models.Q(blocker=user) | models.Q(blocked=user)).values_list('blocker_id',
                                                                                                        'blocked_id')
        return {x for pair in pairs for x in pair} - {user.pk}


class BannedIdentity(models.Model):
    """Чёрный список: номер телефона или Telegram-аккаунт заблокированного человека.

    Хранится не сам номер, а его отпечаток (SHA-256), поэтому по таблице номер не узнать.
    Запись остаётся, даже если аккаунт удалят: заново подтвердить этот номер
    или войти этим Telegram нельзя. Разблокировать — удалить запись (или действие в «Пользователях»).
    """

    PHONE, TELEGRAM = 'phone', 'telegram'
    KINDS = [(PHONE, 'номер телефона'), (TELEGRAM, 'Telegram-аккаунт')]

    kind = models.CharField('что', max_length=10, choices=KINDS)
    key = models.CharField('отпечаток', max_length=64, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='аккаунт', null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='bans')
    reason = models.CharField('причина', max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='кто заблокировал', null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField('когда', auto_now_add=True)

    class Meta:
        verbose_name = 'чёрный список'
        verbose_name_plural = 'чёрный список (номера и Telegram)'
        constraints = [models.UniqueConstraint(fields=['kind', 'key'], name='one_ban_per_identity')]

    def __str__(self):
        return f'{self.get_kind_display()} — {self.user or "удалённый аккаунт"}'
