"""Пуш-уведомления на телефон: каждое уведомление ilm4 (колокольчик) уходит и пушем.

Expo Push Service — бесплатный, один запрос для Android и iOS. Отправка после
сохранения в базе и в отдельном потоке: медленный ответ сервиса пушей не
задерживает сайт. Токен устарел (приложение удалено) — строка удаляется.
"""
import json
import logging
import threading
import urllib.request

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

log = logging.getLogger(__name__)
EXPO_URL = 'https://exp.host/--/api/v2/push/send'


def _send(messages: list) -> None:
    from .models import PushDevice
    try:
        req = urllib.request.Request(EXPO_URL, data=json.dumps(messages).encode(), headers={
            'Content-Type': 'application/json', 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode()).get('data') or []
    except Exception:
        log.warning('Expo push не отправлен', exc_info=True)
        return
    dead = [m['to'] for m, r in zip(messages, result)
            if isinstance(r, dict) and (r.get('details') or {}).get('error') == 'DeviceNotRegistered']
    if dead:
        PushDevice.objects.filter(token__in=dead).delete()


def send_to_user(user_id: int, body: str, url: str = '', title: str = 'ilm4') -> None:
    from django.conf import settings

    from .models import PushDevice
    tokens = list(PushDevice.objects.filter(user_id=user_id).values_list('token', flat=True))
    if not tokens or getattr(settings, 'PUSH_DISABLED', False):
        return
    msgs = [{'to': t, 'title': title, 'body': body[:180], 'sound': 'default', 'data': {'url': url}} for t in tokens]
    threading.Thread(target=_send, args=(msgs,), daemon=True).start()


@receiver(post_save, sender='core.Notification')
def notification_push(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(lambda: send_to_user(instance.user_id, instance.text, instance.url))
