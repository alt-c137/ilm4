"""Автору — уведомление, когда модератор одобрил или отклонил его публикацию."""
from django.db.models.signals import post_save, pre_save

from .models import Moderation
from .publications import PUBLICATIONS

TEXT = {Moderation.APPROVED: '✅ «{t}» одобрено и опубликовано.',
        Moderation.REJECTED: '❌ «{t}» не прошло проверку. Исправьте и отправьте снова (Мои публикации).'}


def _remember(sender, instance, **kwargs):
    if instance.pk:
        instance._old_status = sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first()


def _notify(sender, instance, created, **kwargs):
    old = getattr(instance, '_old_status', None)
    new = getattr(instance, 'status', None)
    if created or old == new or new not in TEXT:
        return
    pub = next(p for p in PUBLICATIONS if p.get_model() is sender)
    owner = getattr(instance, pub.owner, None)
    if owner is None:
        return
    from apps.core.models import Notification
    text = TEXT[new].format(t=pub.title_of(instance)[:80])
    Notification.objects.create(user=owner, text=text, url=pub.url_of(instance) if new == Moderation.APPROVED
                                else '/my/')
    from apps.accounts.telegram import send_message
    send_message(owner, text, '/my/')   # сама глушит сетевые ошибки — сохранение не сломается


def set_status(queryset, status) -> int:
    """Смена статуса из админки по одному объекту — чтобы сработали уведомления авторам."""
    n = 0
    for obj in queryset:
        if obj.status != status:
            obj.status = status
            obj.save(update_fields=['status'])
            n += 1
    return n


def connect():
    for pub in PUBLICATIONS:
        model = pub.get_model()
        pre_save.connect(_remember, sender=model, dispatch_uid=f'pub_remember_{pub.key}')
        post_save.connect(_notify, sender=model, dispatch_uid=f'pub_notify_{pub.key}')
