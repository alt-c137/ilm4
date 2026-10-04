"""Запись в журнал действий (AuditLog) + сигналы входа/выхода админов."""
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import AuditLog


def log_action(request, action: str, target: str = '') -> None:
    """Записать действие текущего пользователя в журнал.

    Устойчиво к «голым» request'ам от сигналов (request.user может отсутствовать).
    """
    from apps.core.limits import client_ip
    user = getattr(request, 'user', None)
    AuditLog.objects.create(
        user=user if (user is not None and user.is_authenticated) else None,
        action=action,
        target=target,
        ip=client_ip(request) or None,         # тот же адрес, что и в лимитах входа (не адрес nginx)
    )


@receiver(user_logged_in)
def _on_login(sender, request, user, **kwargs):
    if user.is_staff:
        log_action(request, 'Вход администратора', user.email)


@receiver(user_logged_out)
def _on_logout(sender, request, user, **kwargs):
    if user and user.is_staff:
        log_action(request, 'Выход администратора', user.email)
