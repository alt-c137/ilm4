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
        'меня можно найти по номеру', default=False,
        help_text='Друзья, у которых ваш номер в контактах, увидят, что вы на ilm4')
    telegram_id = models.BigIntegerField('Telegram ID', null=True, blank=True, unique=True,
                                         help_text='Заполняется при входе из Telegram (мини-приложение)')
    telegram_username = models.CharField('Telegram @', max_length=64, blank=True)
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
        return self.nickname or self.first_name or self.username

    def __str__(self):
        return f'{self.get_display_name()} ({self.email})'


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
