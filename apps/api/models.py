"""Вход мобильного приложения: токены (в базе — только хеш) и устройства для пушей."""
import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class ApiToken(models.Model):
    """Токен входа приложения. Сам токен знает только телефон — в базе его хеш:
    утечка базы не даёт войти в чужие аккаунты. Выход = удаление строки."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_tokens')
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    name = models.CharField('устройство', max_length=80, blank=True)
    created_at = models.DateTimeField('выдан', auto_now_add=True)
    last_used_at = models.DateTimeField('последний раз', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'вход в приложении'
        verbose_name_plural = 'входы в приложении'

    def __str__(self):
        return f'{self.user} · {self.name or "?"}'

    @classmethod
    def issue(cls, user, name: str = '') -> str:
        raw = secrets.token_urlsafe(32)
        cls.objects.create(user=user, key_hash=_hash(raw), name=name[:80])
        return raw

    @classmethod
    def lookup(cls, raw: str):
        if not raw or len(raw) > 100:
            return None
        tok = cls.objects.select_related('user').filter(key_hash=_hash(raw)).first()
        if tok is None or not tok.user.is_active:
            return None
        now = timezone.now()
        if not tok.last_used_at or (now - tok.last_used_at).total_seconds() > 3600:
            cls.objects.filter(pk=tok.pk).update(last_used_at=now)
        return tok


class PushDevice(models.Model):
    """Телефон для пуш-уведомлений (Expo Push: Android и iOS одним способом)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_devices')
    token = models.CharField('push-токен', max_length=200, unique=True)
    platform = models.CharField('платформа', max_length=10, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'телефон для пушей'
        verbose_name_plural = 'телефоны для пушей'

    def __str__(self):
        return f'{self.user} · {self.platform}'
