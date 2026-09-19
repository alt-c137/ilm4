"""WebSocket-потребитель чата: /ws/chat/<thread_id>/.

Подключиться могут только участники диалога. Сообщение сохраняется в БД
и рассылается обоим через group_send.
"""
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.thread_id = self.scope['url_route']['kwargs']['thread_id']
        self.group = f'chat_{self.thread_id}'
        if not self.user.is_authenticated or not await self._is_participant():
            await self.close()
            return
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group'):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content):
        body = (content.get('body') or '').strip()
        if not body or len(body) > 2000:
            return
        message = await self._save_message(body)
        await self.channel_layer.group_send(self.group, {
            'type': 'chat.message',
            'id': message['id'],
            'sender_id': self.user.id,
            'sender_name': self.user.get_display_name(),
            'body': body,
            'created_at': message['created_at'],
        })
        await self._notify_recipient(body)

    async def chat_message(self, event):
        # доставка всем участникам группы
        await self.send_json({
            'id': event['id'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'body': event['body'],
            'created_at': event['created_at'],
        })

    @database_sync_to_async
    def _is_participant(self):
        from .models import Thread

        return Thread.objects.filter(pk=self.thread_id,
                                     participants=self.user).exists()

    @database_sync_to_async
    def _save_message(self, body):
        from .models import Message, Thread

        thread = Thread.objects.get(pk=self.thread_id)
        message = Message.objects.create(thread=thread, sender=self.user, body=body)
        return {'id': message.id,
                'created_at': message.created_at.strftime('%d.%m %H:%M')}

    @database_sync_to_async
    def _notify_recipient(self, body):
        """Получателю — уведомление-колокольчик."""
        from apps.core.models import Notification

        from .models import Thread

        thread = Thread.objects.prefetch_related('participants').get(pk=self.thread_id)
        text = f'{self.user.get_display_name()}: {body[:80]}'
        for participant in thread.participants.all():
            if participant.pk != self.user.pk:
                Notification.objects.create(
                    user=participant, text=text, url=f'/chat/{thread.pk}/')

