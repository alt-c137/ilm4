import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy


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
    # к чему относится чат: ключ раздела (buy, jobs, services, transport, doctors… / nikah / support) и id объекта.
    # Свой чат на каждое объявление (как на Avito); пусто — обычный личный чат. От типа зависят папка и правила.
    context_type = models.CharField('раздел', max_length=20, blank=True, db_index=True)
    context_id = models.PositiveBigIntegerField('объект раздела', null=True, blank=True)
    updated_at = models.DateTimeField('обновлён', auto_now=True, db_index=True)
    # --- группы и каналы (rooms.py). У личных диалогов эти поля пустые ---
    about = models.TextField('описание', blank=True, max_length=500)
    avatar = models.ImageField('аватар', upload_to='chat_avatars/', blank=True, null=True)
    handle = models.CharField('публичное имя (адрес /c/имя/)', max_length=32, blank=True, null=True, unique=True)
    is_public = models.BooleanField('публичный', default=False,
                                    help_text='Виден в каталоге, вступить может любой. Иначе — только по ссылке-приглашению')
    invite_code = models.CharField('код приглашения', max_length=24, blank=True, db_index=True)
    only_admins_post = models.BooleanField('пишут только админы', default=False,
                                           help_text='Для группы. В канале всегда пишут только владелец и админы')
    members_count = models.PositiveIntegerField('участников', default=0)
    platform_verified = models.BooleanField('официальный (галочка ilm4)', default=False,
                                            help_text='Мечеть, учитель, организация — проверено командой ilm4')
    closed = models.BooleanField('закрыт модератором', default=False,
                                 help_text='Нельзя писать и вступать, пропадает из каталога')

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'диалог'
        verbose_name_plural = 'диалоги'

    def __str__(self):
        return _('Диалог #{v1} ({v3} участников)').format(v1=self.pk, v3=self.participants.count())

    # папки в списке чатов (как папки Telegram): раздел → папка
    FOLDERS = [('personal', _lazy('Личные')), ('groups', _lazy('Группы')), ('channels', _lazy('Каналы')),
               ('nikah', _lazy('Никях')), ('buy', _lazy('Покупки')),
               ('work', _lazy('Работа')), ('services', _lazy('Услуги')), ('support', _lazy('Поддержка'))]
    FOLDER_OF = {'': 'personal', 'nikah': 'nikah', 'buy': 'buy', 'jobs': 'work', 'support': 'support'}

    @property
    def folder(self) -> str:
        if self.kind == self.GROUP:
            return 'groups'
        if self.kind == self.CHANNEL:
            return 'channels'
        return self.FOLDER_OF.get(self.context_type, 'services')

    @property
    def is_room(self) -> bool:
        """Группа или канал (не личный диалог)."""
        return self.kind != self.DIRECT

    @property
    def is_channel(self) -> bool:
        return self.kind == self.CHANNEL

    def other_participant(self, user):
        others = self.participants.exclude(pk=user.pk)
        return others.exclude(pk__in=self.observers.values('pk')).first() or others.first()


class Room(Thread):
    """Группа или канал — тот же Thread, отдельное имя для админки (личных диалогов там нет)."""

    class Meta:
        proxy = True
        verbose_name = 'группа / канал'
        verbose_name_plural = 'группы и каналы'


class Member(models.Model):
    """Участник группы / подписчик канала: роль, «без звука», до какого момента прочитано.

    Сам список участников — Thread.participants (на нём держатся доступ и рассылка);
    здесь — то, чего в личном диалоге нет. Удалённый админом остаётся строкой с ролью
    «banned» и не может вернуться по ссылке."""

    OWNER, ADMIN, MEMBER, BANNED = 'owner', 'admin', 'member', 'banned'
    ROLES = [(OWNER, _lazy('Владелец')), (ADMIN, _lazy('Админ')), (MEMBER, _lazy('Участник')), (BANNED, _lazy('Удалён'))]

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_memberships')
    role = models.CharField('роль', max_length=8, choices=ROLES, default=MEMBER)
    muted = models.BooleanField('без звука', default=False)
    last_read_at = models.DateTimeField('прочитано до', null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['thread', 'user'], name='one_membership')]
        indexes = [models.Index(fields=['user', 'thread'])]
        verbose_name = 'участник группы / канала'
        verbose_name_plural = 'участники групп и каналов'

    def __str__(self):
        return f'{self.user} в #{self.thread_id} ({self.role})'

    @property
    def is_admin(self) -> bool:
        return self.role in (self.OWNER, self.ADMIN)


class ThreadKey(models.Model):
    """Ключ чата (DEK), зашифрованный главным ключом (KEK). Сам главный ключ в базе не хранится.
    См. keyring.py и docs/MESSENGER.md §2.1."""

    thread = models.OneToOneField(Thread, on_delete=models.CASCADE, primary_key=True, related_name='key')
    kid = models.CharField('главный ключ (id)', max_length=32)
    wrapped = models.TextField('ключ чата (зашифрован)')
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'ключ чата'
        verbose_name_plural = 'ключи чатов'


class Upload(models.Model):
    """Загрузка большого файла частями (как в Telegram): файл до 2 ГБ идёт кусками по 4 МБ,
    обрыв связи не начинает всё заново. Каждая часть сразу шифруется ключом чата и дописывается
    в файл — открытого текста на диске нет. После последней части запись превращается в сообщение."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='uploads')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_uploads')
    kind = models.CharField(max_length=8, default='file')
    path = models.CharField('файл (внутри MEDIA_ROOT)', max_length=200)
    size = models.BigIntegerField('полный размер, байт')
    received = models.BigIntegerField('получено, байт', default=0)
    info_enc = models.TextField('имя, подпись, время отправки (зашифрованы)', blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'загрузка файла'
        verbose_name_plural = 'загрузки файлов'


class MessageQuerySet(models.QuerySet):
    def delivered(self):
        """Отправленные (не ждущие своего времени)."""
        return self.filter(scheduled_at__isnull=True)

    def visible_to(self, user):
        """Что видит человек: отправленные + свои запланированные."""
        return self.filter(models.Q(scheduled_at__isnull=True) | models.Q(sender=user))


class Message(models.Model):
    """Сообщение в диалоге. Доставку в реальном времени делает Channels (consumers).

    Текст в базе — ``body_enc`` (зашифрован ключом чата, keyring.py). В коде работаем
    с ``message.body`` — расшифровка при чтении и шифрование при сохранении происходят сами.
    """

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='sent_messages')
    TEXT, PHOTO, VIDEO, VOICE, CIRCLE, FILE, SYSTEM = 'text', 'photo', 'video', 'voice', 'circle', 'file', 'system'
    KINDS = [(TEXT, _lazy('Текст')), (PHOTO, _lazy('Фото')), (VIDEO, _lazy('Видео')), (VOICE, _lazy('Голосовое')),
             (CIRCLE, _lazy('Видеокружок')), (FILE, _lazy('Файл')), (SYSTEM, _lazy('Служебное'))]

    kind = models.CharField('вид', max_length=8, choices=KINDS, default=TEXT)
    body_enc = models.TextField('текст (зашифрован)', blank=True, db_column='body')
    # вложение лежит на диске зашифрованным (*.enc, filecrypt.py)
    attachment = models.FileField('вложение', upload_to='chat/%Y/%m/', blank=True, null=True)
    duration = models.PositiveIntegerField('длительность, сек (голос/кружок/видео)', null=True, blank=True)
    # сведения о файле (имя, размер) — зашифрованный JSON: имя файла тоже может быть личным
    meta_enc = models.TextField('сведения о вложении (зашифрованы)', blank=True)
    created_at = models.DateTimeField('создано', auto_now_add=True, db_index=True)
    read_at = models.DateTimeField('прочитано', null=True, blank=True)
    silent = models.BooleanField('без звука', default=False)
    scheduled_at = models.DateTimeField('отправить в (запланированное)', null=True, blank=True, db_index=True)
    views = models.PositiveIntegerField('просмотры (посты канала)', default=0)

    objects = MessageQuerySet.as_manager()

    _plain = None
    _plain_dirty = False

    class Meta:
        ordering = ['created_at']
        verbose_name = 'сообщение'
        verbose_name_plural = 'сообщения'

    @property
    def body(self) -> str:
        if self._plain is None:
            from .keyring import decrypt_text
            self._plain = decrypt_text(self.thread_id, self.body_enc) if self.body_enc else ''
        return self._plain

    @body.setter
    def body(self, value):
        self._plain = value or ''
        self._plain_dirty = True

    def save(self, *args, **kwargs):
        if self._plain_dirty:
            from .keyring import encrypt_text
            self.body_enc = encrypt_text(self.thread_id, self._plain)
            self._plain_dirty = False
            fields = kwargs.get('update_fields')
            if fields is not None and 'body' in fields:
                kwargs['update_fields'] = [f if f != 'body' else 'body_enc' for f in fields]
        super().save(*args, **kwargs)

    @property
    def meta(self) -> dict:
        if not self.meta_enc:
            return {}
        import json

        from .keyring import decrypt_text
        try:
            return json.loads(decrypt_text(self.thread_id, self.meta_enc))
        except ValueError:
            return {}

    def set_meta(self, **data) -> None:
        import json

        from .keyring import encrypt_text
        self.meta_enc = encrypt_text(self.thread_id, json.dumps(data, ensure_ascii=False))

    @property
    def is_scheduled(self) -> bool:
        return self.scheduled_at is not None

    def __str__(self):
        return f'{self.sender}: {self.kind} #{self.pk}'
