from django.conf import settings
from django.db import models
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from .crypto import EncryptedTextField


class Thread(models.Model):
    """Диалог. Сейчас — личный (двое). Поля kind/title/owner — основа для групп
    и каналов (фаза «мессенджер»): включаются без переделки таблиц."""

    DIRECT, GROUP, CHANNEL = 'direct', 'group', 'channel'
    KINDS = [(DIRECT, _lazy('Личный')), (GROUP, _lazy('Группа')), (CHANNEL, _lazy('Канал'))]

    kind = models.CharField('вид', max_length=8, choices=KINDS, default=DIRECT, db_index=True)
    title = models.CharField('название (группа/канал)', max_length=120, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='owned_threads', verbose_name='создатель (группа/канал)')
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='chat_threads')
    # свидетели (махрам в никяхе): тоже участники, но не «собеседник» в заголовке диалога
    observers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='observed_threads', blank=True,
                                       verbose_name='свидетели')
    subject = models.CharField('тема (например, объявление)', max_length=160, blank=True)
    updated_at = models.DateTimeField('обновлён', auto_now=True, db_index=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'диалог'
        verbose_name_plural = 'диалоги'

    def __str__(self):
        return _('Диалог #{v1} ({v3} участников)').format(v1=self.pk, v3=self.participants.count())

    def other_participant(self, user):
        others = self.participants.exclude(pk=user.pk)
        return others.exclude(pk__in=self.observers.values('pk')).first() or others.first()


class Message(models.Model):
    """Сообщение в диалоге. Доставку в реальном времени делает Channels (consumers)."""

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='sent_messages')
    TEXT, PHOTO, VIDEO, VOICE, CIRCLE, FILE, SYSTEM = 'text', 'photo', 'video', 'voice', 'circle', 'file', 'system'
    KINDS = [(TEXT, _lazy('Текст')), (PHOTO, _lazy('Фото')), (VIDEO, _lazy('Видео')), (VOICE, _lazy('Голосовое')),
             (CIRCLE, _lazy('Видеокружок')), (FILE, _lazy('Файл')), (SYSTEM, _lazy('Служебное'))]

    kind = models.CharField('вид', max_length=8, choices=KINDS, default=TEXT)
    body = EncryptedTextField('текст', blank=True)  # в БД — зашифровано
    # вложения — основа на будущее: фото/видео/голос/кружок (сейчас в интерфейсе выключены)
    attachment = models.FileField('вложение', upload_to='chat/%Y/%m/', blank=True, null=True)
    duration = models.PositiveIntegerField('длительность, сек (голос/кружок/видео)', null=True, blank=True)
    created_at = models.DateTimeField('создано', auto_now_add=True, db_index=True)
    read_at = models.DateTimeField('прочитано', null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'сообщение'
        verbose_name_plural = 'сообщения'

    def __str__(self):
        return f'{self.sender}: {self.body[:40]}'
