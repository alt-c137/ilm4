from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Единый пользователь платформы (PASSPORT §7.2).

    Кастомная модель объявлена с первого дня: менять AUTH_USER_MODEL после
    первых миграций — больно. Email-логин, ник, аватар, город, роли/2FA
    добавляются в фазе 1 (accounts).
    """
