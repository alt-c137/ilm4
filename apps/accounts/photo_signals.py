"""Фото профиля копятся, как в Telegram: поставил новый аватар — прежний остаётся в истории и листается.

Аватар меняют из разных мест (профиль на сайте, приложение, вход через Telegram, админка), поэтому
историю ведём сигналом на сохранение пользователя, а не в каждом из этих мест."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import User


def _touches_avatar(update_fields) -> bool:
    return update_fields is None or 'avatar' in update_fields


@receiver(pre_save, sender=User)
def keep_old_avatar(sender, instance, update_fields=None, **kwargs):
    if not instance.pk or not _touches_avatar(update_fields):
        return
    old = User.objects.filter(pk=instance.pk).values_list('avatar', flat=True).first()
    new = instance.avatar.name if instance.avatar else ''
    if old and old != new:
        from .models import ProfilePhoto
        if not ProfilePhoto.objects.filter(user_id=instance.pk, image=old).exists():
            ProfilePhoto.objects.create(user_id=instance.pk, image=old)


@receiver(post_save, sender=User)
def add_new_avatar(sender, instance, update_fields=None, **kwargs):
    if not _touches_avatar(update_fields) or not instance.avatar:
        return
    from . import people
    people.add_photo(instance, instance.avatar.name)
