"""Блокировка нарушителя: аккаунт выключается, публикации снимаются, номер и Telegram — в чёрный список.

Новая почта мошенника не поможет: публиковать можно только с подтверждённым номером,
а его номер (и Telegram-аккаунт, через который номер подтверждается) заблокированы навсегда.
"""
import hashlib

from django.db import transaction
from django.utils.translation import gettext as _

from .models import AuditLog, BannedIdentity


def tg_key(tg_id) -> str:
    return hashlib.sha256(f'tg:{tg_id}'.encode()).hexdigest()


def phone_banned(phone_key: str) -> bool:
    return bool(phone_key) and BannedIdentity.objects.filter(kind=BannedIdentity.PHONE, key=phone_key).exists()


def tg_banned(tg_id) -> bool:
    return bool(tg_id) and BannedIdentity.objects.filter(kind=BannedIdentity.TELEGRAM, key=tg_key(tg_id)).exists()


def can_ban(by, user) -> bool:
    return (by.is_authenticated and by.is_staff and by.has_perm('accounts.change_user')
            and user.pk != by.pk and not user.is_staff and not user.is_superuser)


@transaction.atomic
def ban(user, by=None, reason: str = '') -> int:
    """Заблокировать. Возвращает, сколько публикаций снято."""
    from apps.core.models import Moderation
    from apps.core.publications import PUBLICATIONS

    user.is_active = False
    user.save(update_fields=['is_active'])
    for kind, key in ((BannedIdentity.PHONE, user.phone_key if user.phone_verified else ''),
                      (BannedIdentity.TELEGRAM, tg_key(user.telegram_id) if user.telegram_id else '')):
        if key:
            BannedIdentity.objects.update_or_create(kind=kind, key=key, defaults={
                'user': user, 'reason': reason[:300], 'created_by': by if by and by.is_authenticated else None})
    hidden = 0
    for pub in PUBLICATIONS:               # без уведомлений автору: queryset.update не шлёт сигналы
        model = pub.get_model()
        if hasattr(model, 'status'):
            hidden += (model.objects.filter(**{pub.owner: user}).exclude(status=Moderation.REJECTED)
                       .update(status=Moderation.REJECTED))
    profile = getattr(user, 'nikah_profile', None)
    if profile is not None:
        type(profile).objects.filter(pk=profile.pk).update(status=Moderation.REJECTED, is_active=False)
    from apps.api.models import ApiToken
    ApiToken.objects.filter(user=user).delete()          # выход из приложения на всех телефонах
    AuditLog.objects.create(user=by if by and by.is_authenticated else None, action='Пользователь заблокирован',
                            target=f'user#{user.pk} {user.email}'[:200] + (f' — {reason}' if reason else ''))
    return hidden


@transaction.atomic
def unban(user, by=None) -> None:
    """Разблокировать аккаунт и убрать его номер и Telegram из чёрного списка.
    Снятые публикации не возвращаются сами: автор отправит их заново, или модератор одобрит."""
    user.is_active = True
    user.save(update_fields=['is_active'])
    BannedIdentity.objects.filter(user=user).delete()
    AuditLog.objects.create(user=by if by and by.is_authenticated else None, action='Пользователь разблокирован',
                            target=f'user#{user.pk} {user.email}'[:200])


def banned_text() -> str:
    return _('Этот номер или Telegram-аккаунт заблокирован за нарушение правил ilm4.')
