from django.conf import settings
from django.db import models


class Thread(models.Model):
    """Личный диалог двух участников (как в Авито)."""

    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='chat_threads')
    subject = models.CharField('тема (например, объявление)', max_length=160, blank=True)
    updated_at = models.DateTimeField('обновлён', auto_now=True, db_index=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'диалог'
        verbose_name_plural = 'диалоги'

    def __str__(self):
        return f'Диалог #{self.pk} ({self.participants.count()} участников)'

    def other_participant(self, user):
        return self.participants.exclude(pk=user.pk).first()


class Message(models.Model):
    """Сообщение в диалоге. Доставку в реальном времени делает Channels (consumers)."""

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='sent_messages')
    body = models.TextField('текст')
    created_at = models.DateTimeField('создано', auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'сообщение'
        verbose_name_plural = 'сообщения'

    def __str__(self):
        return f'{self.sender}: {self.body[:40]}'
