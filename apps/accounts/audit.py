"""Запись в журнал действий (AuditLog) + сигналы входа/выхода админов."""
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import AuditLog


def log_action(request, action: str, target: str = '') -> None:
    """Записать действие текущего пользователя в журнал.

    Устойчиво к «голым» request'ам от сигналов (request.user может отсутствовать).
    """
    user = getattr(request, 'user', None)
    meta = getattr(request, 'META', {}) if request is not None else {}
    AuditLog.objects.create(
        user=user if (user is not None and user.is_authenticated) else None,
        action=action,
        target=target,
        ip=meta.get('REMOTE_ADDR') or None,
    )


@receiver(user_logged_in)
def _on_login(sender, request, user, **kwargs):
    if user.is_staff:
        log_action(request, 'Вход администратора', user.email)


@receiver(user_logged_out)
def _on_logout(sender, request, user, **kwargs):
    if user and user.is_staff:
        log_action(request, 'Выход администратора', user.email)
