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
    # канал сообщества (как в Discord): такие чаты не показываются в общем списке — только внутри сообщества (apps/chat/spaces.py)
    space = models.ForeignKey('Space', null=True, blank=True, on_delete=models.CASCADE, related_name='threads')
    space_category = models.ForeignKey('SpaceCategory', null=True, blank=True, on_delete=models.SET_NULL, related_name='threads')
    space_order = models.PositiveSmallIntegerField(default=0)
    space_private = models.BooleanField('закрытый канал сообщества (только выбранным ролям)', default=False)
    space_topic = models.CharField('тема канала', max_length=200, blank=True)
    protected = models.BooleanField('запретить пересылку и копирование', default=False,
                                    help_text='Как «Запретить копирование» в Telegram: сообщения нельзя переслать')
    reactions_on = models.BooleanField('реакции включены', default=True)
    comments_on = models.BooleanField('комментарии к постам (канал)', default=False)
    slow_seconds = models.PositiveIntegerField('медленный режим, сек (группа)', default=0,
                                               help_text='0 — выключен. Участник пишет не чаще, чем раз в N секунд')

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
    def chat_type(self) -> str:
        """Тип чата для своих папок (как «Контакты / Группы / Каналы / Боты» в Telegram)."""
        if self.kind == self.GROUP:
            return 'groups'
        if self.kind == self.CHANNEL:
            return 'channels'
        if self.context_type == 'nikah':
            return 'nikah'
        if self.context_type in ('', 'support', 'saved'):
            return 'personal'
        return 'ads'

    @property
    def is_saved(self) -> bool:
        """«Избранное» — чат с самим собой."""
        return self.context_type == 'saved'

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
        """Что видит человек: отправленные + свои запланированные; без удалённых «у себя» и комментариев к постам."""
        return (self.filter(models.Q(scheduled_at__isnull=True) | models.Q(sender=user), comment_of__isnull=True)
                .exclude(hidden_for__user=user))


class Message(models.Model):
    """Сообщение в диалоге. Доставку в реальном времени делает Channels (consumers).

    Текст в базе — ``body_enc`` (зашифрован ключом чата, keyring.py). В коде работаем
    с ``message.body`` — расшифровка при чтении и шифрование при сохранении происходят сами.
    """

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='sent_messages')
    TEXT, PHOTO, VIDEO, VOICE, CIRCLE, FILE, SYSTEM = 'text', 'photo', 'video', 'voice', 'circle', 'file', 'system'
    POLL = 'poll'
    KINDS = [(TEXT, _lazy('Текст')), (PHOTO, _lazy('Фото')), (VIDEO, _lazy('Видео')), (VOICE, _lazy('Голосовое')),
             (CIRCLE, _lazy('Видеокружок')), (FILE, _lazy('Файл')), (SYSTEM, _lazy('Служебное')), (POLL, _lazy('Опрос'))]

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
    # --- как в Telegram: ответ, пересылка, правка, закреп, комментарии к посту ---
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replies',
                                 verbose_name='ответ на')
    # комментарий к посту канала: виден не в ленте, а под постом
    comment_of = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='comments',
                                   verbose_name='комментарий к посту')
    comments_count = models.PositiveIntegerField('комментариев', default=0)
    fwd_enc = models.TextField('переслано от (зашифровано)', blank=True)
    edited_at = models.DateTimeField('изменено', null=True, blank=True)
    pinned_at = models.DateTimeField('закреплено', null=True, blank=True, db_index=True)

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

    @property
    def fwd(self) -> dict:
        """От кого переслано: {'name', 'user', 'room'} или {}."""
        if not self.fwd_enc:
            return {}
        import json

        from .keyring import decrypt_text
        try:
            return json.loads(decrypt_text(self.thread_id, self.fwd_enc))
        except ValueError:
            return {}

    def set_fwd(self, **data) -> None:
        import json

        from .keyring import encrypt_text
        self.fwd_enc = encrypt_text(self.thread_id, json.dumps(data, ensure_ascii=False))

    def __str__(self):
        return f'{self.sender}: {self.kind} #{self.pk}'


class Reaction(models.Model):
    """Реакция на сообщение. Как в Telegram без Premium: одна реакция от человека на сообщение."""

    EMOJI = ['👍', '❤️', '🤲', '🔥', '😂', '😮', '😢', '👏', '💯', '🙏', '👎', '🤔']

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_reactions')
    emoji = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['message', 'user'], name='one_reaction')]
        verbose_name = 'реакция'
        verbose_name_plural = 'реакции'


class HiddenMessage(models.Model):
    """«Удалить у себя»: сообщение остаётся у собеседника, но этот человек его больше не видит."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hidden_messages')
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='hidden_for')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'message'], name='one_hidden')]
        verbose_name = 'скрытое сообщение'
        verbose_name_plural = 'скрытые сообщения'


class ChatState(models.Model):
    """Личное состояние чата у человека: закреп, архив, «не прочитано», черновик, очистка истории.

    Это то, что в Telegram у каждого своё: я закрепил чат — у собеседника он не закреплён."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_states')
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='states')
    pinned_at = models.DateTimeField('закреплён в общем списке', null=True, blank=True)
    archived = models.BooleanField('в архиве', default=False)
    unread_mark = models.BooleanField('помечен непрочитанным', default=False)
    draft_enc = models.TextField('черновик (зашифрован)', blank=True)
    cleared_at = models.DateTimeField('история очищена до', null=True, blank=True)
    hidden = models.BooleanField('убран из списка (до нового сообщения)', default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'thread'], name='one_chat_state')]
        verbose_name = 'состояние чата'
        verbose_name_plural = 'состояния чатов'


class ChatFolder(models.Model):
    """Своя папка чатов — как в Telegram: человек сам задаёт название, какие типы чатов в неё входят,
    какие чаты добавить или убрать поимённо и что исключить (без звука, прочитанные, архив)."""

    TYPES = [('personal', _lazy('Личные')), ('ads', _lazy('По объявлениям')), ('nikah', _lazy('Никях')),
             ('groups', _lazy('Группы')), ('channels', _lazy('Каналы')), ('bots', _lazy('Боты'))]
    MAX_FOLDERS = 10          # как в Telegram без Premium
    MAX_CHATS = 100           # чатов, выбранных поимённо

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_folders')
    title = models.CharField('название', max_length=24)
    emoji = models.CharField('значок', max_length=8, blank=True)
    order = models.PositiveSmallIntegerField('порядок', default=0)
    types = models.JSONField('типы чатов', default=list, blank=True)
    no_muted = models.BooleanField('без «без звука»', default=False)
    no_read = models.BooleanField('без прочитанных', default=False)
    no_archived = models.BooleanField('без архивных', default=True)
    include = models.ManyToManyField(Thread, related_name='+', blank=True, verbose_name='всегда включать')
    exclude = models.ManyToManyField(Thread, related_name='+', blank=True, verbose_name='всегда исключать')
    pins = models.JSONField('закреплённые в папке (id чатов по порядку)', default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'pk']
        verbose_name = 'папка чатов'
        verbose_name_plural = 'папки чатов'

    def __str__(self):
        return f'{self.title} ({self.user})'


class Space(models.Model):
    """Сообщество (как сервер в Discord): значок, описание, категории и каналы. Каждый текстовый канал — обычный чат
    (Thread с полем space), поэтому в нём работает всё, что есть в чатах: ответы, реакции, файлы, закрепы, поиск."""

    title = models.CharField('название', max_length=80)
    about = models.CharField('описание', max_length=500, blank=True)
    icon = models.ImageField('значок', upload_to='chat/spaces/', blank=True)
    handle = models.CharField('адрес', max_length=32, unique=True, null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='spaces_owned')
    is_public = models.BooleanField('виден в каталоге, вступить может любой', default=False)
    invite_code = models.CharField(max_length=24, unique=True)
    members_count = models.PositiveIntegerField(default=0)
    platform_verified = models.BooleanField('официальное (галочка ilm4)', default=False)
    closed = models.BooleanField('закрыто модератором', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'сообщество'
        verbose_name_plural = 'сообщества'

    def __str__(self):
        return self.title


class SpaceCategory(models.Model):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='categories')
    title = models.CharField(max_length=60)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'pk']


class SpaceVoice(models.Model):
    """Голосовая комната сообщества. Основа: сама комната заработает с медиасервером LiveKit (нужен сервер)."""

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='voices')
    category = models.ForeignKey(SpaceCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name='voices')
    title = models.CharField(max_length=60)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'pk']


class SpaceMember(models.Model):
    """Участник сообщества: роль и свой ник здесь (как в Discord — в каждом сообществе можно зваться по-своему)."""

    OWNER, ADMIN, MOD, MEMBER, BANNED = 'owner', 'admin', 'mod', 'member', 'banned'
    ROLES = [(OWNER, _lazy('Владелец')), (ADMIN, _lazy('Админ')), (MOD, _lazy('Модератор')), (MEMBER, _lazy('Участник')), (BANNED, _lazy('Удалён'))]

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='space_memberships')
    role = models.CharField('роль', max_length=8, choices=ROLES, default=MEMBER)
    nick = models.CharField('ник в сообществе', max_length=32, blank=True)
    roles = models.ManyToManyField('SpaceRole', blank=True, related_name='holders')     # свои роли сообщества (цвет, права)
    muted_until = models.DateTimeField('тайм-аут до', null=True, blank=True)            # не может писать до этого времени
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['space', 'user'], name='one_space_membership')]
        indexes = [models.Index(fields=['user', 'space'])]
        verbose_name = 'участник сообщества'
        verbose_name_plural = 'участники сообществ'

    @property
    def is_admin(self) -> bool:
        return self.role in (self.OWNER, self.ADMIN)

    @property
    def can_moderate(self) -> bool:
        return self.role in (self.OWNER, self.ADMIN, self.MOD)


class SpaceRole(models.Model):
    """Своя роль сообщества — как в Discord: название, цвет, права; по ролям открываются закрытые каналы."""

    PERMS = [('manage_space', _lazy('Настройки сообщества')), ('manage_roles', _lazy('Роли')), ('manage_channels', _lazy('Каналы и категории')),
             ('kick', _lazy('Удалять участников')), ('timeout', _lazy('Тайм-аут участникам')), ('delete_messages', _lazy('Удалять и закреплять сообщения')),
             ('mention_everyone', _lazy('Упоминать @everyone')), ('manage_tasks', _lazy('Доска задач: менять любые задачи'))]

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=32)
    color = models.CharField(max_length=7, default='#6d5efc')
    perms = models.JSONField(default=list, blank=True)
    hoist = models.BooleanField('показывать отдельной группой в списке участников', default=True)
    order = models.PositiveSmallIntegerField(default=0)
    private_threads = models.ManyToManyField(Thread, blank=True, related_name='space_roles_allowed')   # закрытые каналы, куда пускает роль

    class Meta:
        ordering = ['order', 'pk']


class SpaceInvite(models.Model):
    """Приглашение со сроком и числом использований (как в Discord). Постоянная ссылка — Space.invite_code."""

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='invites')
    code = models.CharField(max_length=24, unique=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    expires_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(default=0)               # 0 — без ограничения
    uses = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pk']


class SpaceLog(models.Model):
    """Журнал действий в сообществе (кто что изменил) — виден тем, кто управляет сообществом."""

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='logs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    action = models.CharField(max_length=24)
    text = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pk']


class SpaceTask(models.Model):
    """Задача на доске сообщества (канбан): идеи → делаем → готово. Для совместных проектов."""

    TODO, DOING, DONE = 'todo', 'doing', 'done'
    STATUSES = [(TODO, _lazy('Идеи и задачи')), (DOING, _lazy('Делаем')), (DONE, _lazy('Готово'))]

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=160)
    note = models.CharField(max_length=1000, blank=True)
    status = models.CharField(max_length=6, choices=STATUSES, default=TODO)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='space_tasks')
    due = models.DateField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'pk']
