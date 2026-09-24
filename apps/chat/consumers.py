"""WebSocket чата.

/ws/chat/<thread_id>/ — диалог: сообщения, «прочитано», сигналинг звонков (WebRTC).
/ws/me/               — личный канал пользователя: входящие звонки на любой странице.

Подключаются только участники диалога. Текст сохраняется зашифрованным (см. crypto.py).
Звонки: браузеры соединяются напрямую (WebRTC), сервер лишь передаёт служебные
сигналы (offer/answer/ice) — медиа через наш сервер не идёт.
"""
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

SIGNAL_ACTIONS = {'ring', 'accept', 'decline', 'offer', 'answer', 'ice', 'end', 'busy'}
# защита от флуда: не больше N сообщений за окно (сигналы звонка — отдельно, их много)
MSG_LIMIT, MSG_WINDOW = 20, 10
SIGNAL_LIMIT, SIGNAL_WINDOW = 300, 60


def _allow(bucket: list, limit: int, window: int) -> bool:
    now = time.monotonic()
    while bucket and now - bucket[0] > window:
        bucket.pop(0)
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.thread_id = self.scope['url_route']['kwargs']['thread_id']
        self.group = f'chat_{self.thread_id}'
        if not self.user.is_authenticated or not await self._is_participant():
            await self.close()
            return
        self._msgs, self._signals = [], []
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group'):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content):
        if content.get('type') == 'signal':
            if not _allow(self._signals, SIGNAL_LIMIT, SIGNAL_WINDOW):
                return
            if not await self._calls_allowed(bool(content.get('video'))):
                return   # звонки выключены в админке — сигналы не пересылаем
            await self._signal(content)
            return
        if not _allow(self._msgs, MSG_LIMIT, MSG_WINDOW):
            await self.send_json({'type': 'error', 'error': 'Слишком часто — подождите немного.'})
            return
        if content.get('type') == 'calllog':
            payload = await self._call_log(content)
            if payload:
                await self.channel_layer.group_send(self.group, {'type': 'chat.message', 'payload': payload})
            return
        body = (content.get('body') or '').strip()
        if not body or len(body) > 2000:
            return
        if await self._blocked():
            await self.send_json({'type': 'error', 'error': 'Переписка недоступна: блокировка'})
            return
        payload = await self._save_message(body)
        await self.channel_layer.group_send(self.group, {'type': 'chat.message', 'payload': payload})
        await self._notify_recipient(body)

    async def chat_message(self, event):
        # поддержка старого формата события (без payload)
        payload = event.get('payload') or {k: v for k, v in event.items() if k != 'type'}
        await self.send_json({'type': 'msg', **payload})
        # получатель сейчас в диалоге — сообщение прочитано, отправителю ✓✓
        if payload['sender_id'] != self.user.id:
            await self._mark_read(payload['id'])
            await self.channel_layer.group_send(self.group, {'type': 'chat.read', 'ids': [payload['id']],
                                                             'reader_id': self.user.id})

    async def chat_read(self, event):
        if event['reader_id'] != self.user.id:
            await self.send_json({'type': 'read', 'ids': event['ids']})

    # --- звонки: пересылаем сигналы собеседнику ---
    async def _signal(self, content):
        action = content.get('action')
        if action not in SIGNAL_ACTIONS:
            return
        data = {k: content.get(k) for k in ('action', 'sdp', 'candidate', 'video') if k in content}
        await self.channel_layer.group_send(self.group, {'type': 'chat.signal', 'sender_id': self.user.id, 'data': data})
        if action in ('ring', 'end', 'decline', 'accept'):
            # на любую страницу сайта — всплывашка «входящий звонок» / её закрытие
            for uid in await self._others():
                await self.channel_layer.group_send(f'user_{uid}', {
                    'type': 'user.call', 'action': action, 'thread': int(self.thread_id),
                    'from_name': self.user.get_display_name(), 'video': bool(content.get('video'))})

    async def chat_signal(self, event):
        if event['sender_id'] != self.user.id:
            await self.send_json({'type': 'signal', **event['data']})

    @database_sync_to_async
    def _calls_allowed(self, video: bool) -> bool:
        from apps.core.models import SiteSettings

        st = SiteSettings.get_solo()
        return st.chat_video_calls_enabled if video else (st.chat_calls_enabled or st.chat_video_calls_enabled)

    @database_sync_to_async
    def _blocked(self):
        from apps.accounts.models import UserBlock

        from .models import Thread
        others = Thread.objects.get(pk=self.thread_id).participants.exclude(pk=self.user.pk)
        return any(UserBlock.between(self.user, o) for o in others)

    @database_sync_to_async
    def _is_participant(self):
        from .models import Thread

        return Thread.objects.filter(pk=self.thread_id, participants=self.user).exists()

    @database_sync_to_async
    def _others(self):
        from .models import Thread

        thread = Thread.objects.get(pk=self.thread_id)
        return list(thread.participants.exclude(pk=self.user.pk).values_list('pk', flat=True))

    @database_sync_to_async
    def _save_message(self, body):
        from .events import message_payload
        from .models import Message, Thread

        thread = Thread.objects.get(pk=self.thread_id)
        message = Message.objects.create(thread=thread, sender=self.user, body=body)
        thread.save(update_fields=['updated_at'])
        return message_payload(message)

    @database_sync_to_async
    def _call_log(self, content):
        """Запись о звонке в переписке (пишет звонивший): длительность или исход."""
        from .events import message_payload
        from .models import Message, Thread

        video = bool(content.get('video'))
        outcome = content.get('outcome')
        try:
            sec = max(0, min(int(content.get('duration') or 0), 6 * 3600))
        except (TypeError, ValueError):
            sec = 0
        kind = 'Видеозвонок' if video else 'Аудиозвонок'
        text = {
            'done': f'{kind} · {sec // 60}:{sec % 60:02d}',
            'declined': f'{kind} отклонён',
            'missed': f'Пропущенный {kind.lower()}',
            'cancelled': f'{kind} отменён',
        }.get(outcome)
        if not text:
            return None
        thread = Thread.objects.get(pk=self.thread_id)
        m = Message.objects.create(thread=thread, sender=self.user, kind=Message.SYSTEM, body=text,
                                   duration=sec or None)
        thread.save(update_fields=['updated_at'])
        return message_payload(m)

    @database_sync_to_async
    def _mark_read(self, message_id):
        from django.utils import timezone

        from .models import Message

        Message.objects.filter(pk=message_id, read_at__isnull=True).update(read_at=timezone.now())

    @database_sync_to_async
    def _notify_recipient(self, body):
        from .events import notify_recipients
        from .models import Thread

        notify_recipients(Thread.objects.get(pk=self.thread_id), self.user, body)


class UserConsumer(AsyncJsonWebsocketConsumer):
    """Личный канал: входящий звонок показывается на любой странице сайта."""

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return
        self.group = f'user_{self.user.pk}'
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group'):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def user_call(self, event):
        await self.send_json({k: v for k, v in event.items() if k != 'type'})
