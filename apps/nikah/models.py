"""Никях: анкета, интерес («❤»), сохранённые, пара (взаимный интерес → обмен фото → чат).

Принципы раздела:
- в ленте анкеты без фото — решение по убеждениям и описанию;
- фото хранится зашифрованным и показывается только при взаимном интересе,
  один раз, ограниченное время, с водяным знаком ID смотрящего; сестра — первой;
- ответы на закрытые вопросы о религии видит только модератор;
- контакты в анкете запрещены (проверка при сохранении и модерация).
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _lazy

from apps.core.models import Moderation

from . import choices as C


class NikahProfile(models.Model):
    GENDERS = [('M', _lazy('Брат')), ('F', _lazy('Сестра'))]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='nikah_profile')
    gender = models.CharField('кто', max_length=1, choices=GENDERS)
    name = models.CharField('имя или ник', max_length=40, blank=True)
    age = models.PositiveSmallIntegerField('возраст')
    age_from = models.PositiveSmallIntegerField('ищу возраст от', default=18)
    age_to = models.PositiveSmallIntegerField('ищу возраст до', default=60)

    country = models.CharField('страна', max_length=80, blank=True)
    city = models.CharField('город', max_length=80, blank=True)
    nationality = models.CharField('национальность', max_length=80, blank=True)

    height = models.PositiveSmallIntegerField('рост, см', null=True, blank=True)
    weight = models.PositiveSmallIntegerField('вес, кг', null=True, blank=True)

    marital = models.CharField('семейное положение', max_length=10, choices=C.model_choices(C.MARITAL), blank=True)
    wife_number = models.PositiveSmallIntegerField('ищу жену по счёту', choices=C.WIFE_NUMBER, null=True, blank=True)
    polygyny = models.CharField('готова быть не первой женой', max_length=8, choices=C.POLYGYNY, blank=True)

    madhhab = models.CharField('мазхаб', max_length=8, choices=C.model_choices(C.MADHHAB), blank=True)
    aqida = models.CharField('вероубеждение', max_length=10, choices=C.model_choices(C.AQIDA), blank=True)
    prayer = models.CharField('намаз', max_length=10, choices=C.model_choices(C.PRAYER), blank=True)
    quran = models.CharField('чтение Корана', max_length=10, choices=C.model_choices(C.QURAN), blank=True)
    where_allah = models.CharField('где Аллах', max_length=10, choices=C.model_choices(C.WHERE_ALLAH), blank=True)

    has_children = models.CharField('есть свои дети', max_length=4, choices=[('no', _lazy('Нет')), ('yes', _lazy('Есть'))],
                                    blank=True)
    children_want = models.CharField('хочет детей', max_length=8, choices=C.model_choices(C.CHILDREN_WANT), blank=True)
    children_accept = models.CharField('примет детей партнёра', max_length=8,
                                       choices=C.model_choices(C.CHILDREN_ACCEPT), blank=True)
    ready_when = models.CharField('готов к никяху', max_length=8, choices=C.model_choices(C.READY), blank=True)
    look = models.CharField('борода / покрытие', max_length=10, choices=C.LOOK_M + C.LOOK_F, blank=True)
    relocation = models.CharField('переезд', max_length=8, choices=C.model_choices(C.RELOCATION), blank=True)

    manhaj_text = models.TextField('вероубеждение и манхадж (своими словами)', blank=True)
    about = models.TextField('о себе', blank=True)
    partner_expectations = models.TextField('кого ищу', blank=True)

    photo_mode = models.CharField('фото', max_length=10, choices=C.model_choices(C.PHOTO_MODE), default='exchange')
    photo_private = models.FileField('фото (зашифровано)', upload_to='nikah_private/', blank=True, editable=False)
    photo = models.ImageField('фото (старое, не показывается)', upload_to='nikah/%Y/%m/', blank=True, null=True)
    contact_hint = models.CharField('как связаться (устарело)', max_length=200, blank=True)

    faith_answers = models.JSONField('закрытые ответы о религии', default=dict, blank=True,
                                     help_text='Видит только модератор')
    agreed_at = models.DateTimeField('приняты обязательства', null=True, blank=True)

    status = models.CharField('статус', max_length=10, choices=Moderation.CHOICES, default=Moderation.PENDING)
    is_active = models.BooleanField('анкета активна', default=True)
    boosted_until = models.DateTimeField('буст до', null=True, blank=True)
    premium_until = models.DateTimeField('премиум до', null=True, blank=True)
    verified = models.BooleanField('верифицирован(а) ✅', default=False,
                                   help_text='Модератор посмотрел видео-кружок в Telegram: живой человек, лицо совпадает')
    verified_at = models.DateTimeField('верификация', null=True, blank=True)
    referred_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='invited', verbose_name='пригласил(а)')
    ref_bonus_given = models.BooleanField('бонус за приглашение начислен', default=False, editable=False)
    witness = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='nikah_witness_for', verbose_name='свидетель (махрам)',
                                help_text='Видит переписку во всех чатах никяха этой анкеты')
    witness_token = models.CharField(max_length=32, blank=True, editable=False)
    last_seen = models.DateTimeField('был(а) в сети', null=True, blank=True)
    created_at = models.DateTimeField('создано', auto_now_add=True)
    updated_at = models.DateTimeField('изменено', auto_now=True)

    class Meta:
        ordering = ['-boosted_until', '-created_at']
        verbose_name = 'анкета никаха'
        verbose_name_plural = 'анкеты никаха'

    def __str__(self):
        return f'{self.display_name}, {self.age}, {self.city}'

    # --- подписи по полу ---
    @property
    def is_brother(self) -> bool:
        return self.gender == 'M'

    @property
    def display_name(self) -> str:
        return self.name or self.get_gender_display()

    def label(self, field: str) -> str:
        """Значение поля подписью для этого пола: «Разведена», а не «Разведён / Разведена»."""
        value = getattr(self, field)
        if not value:
            return ''
        if field == 'look':
            return dict(C.LOOK_M if self.is_brother else C.LOOK_F).get(value, '')
        if field == 'wife_number':
            return dict(C.WIFE_NUMBER).get(value, '')
        if field == 'polygyny':
            return dict(C.POLYGYNY).get(value, '')
        options = getattr(C, {
            'marital': 'MARITAL', 'madhhab': 'MADHHAB', 'aqida': 'AQIDA', 'prayer': 'PRAYER',
            'quran': 'QURAN', 'where_allah': 'WHERE_ALLAH', 'children_want': 'CHILDREN_WANT',
            'children_accept': 'CHILDREN_ACCEPT', 'ready_when': 'READY', 'relocation': 'RELOCATION',
            'photo_mode': 'PHOTO_MODE'}[field])
        for key, m, f in options:
            if key == value:
                return m if self.is_brother else (f or m)
        return ''

    @property
    def place(self) -> str:
        from django.utils.translation import get_language

        from .geo import country_name
        country = country_name(self.country, (get_language() or 'ru')[:2])
        return ', '.join(x for x in (self.city, country) if x)

    @property
    def is_boosted(self) -> bool:
        return bool(self.boosted_until and self.boosted_until > timezone.now())

    @property
    def is_premium(self) -> bool:
        return bool(self.premium_until and self.premium_until > timezone.now())

    @property
    def is_online(self) -> bool:
        return bool(self.last_seen and timezone.now() - self.last_seen < timedelta(minutes=10))

    @property
    def is_published(self) -> bool:
        return self.status == Moderation.APPROVED and self.is_active

    @property
    def has_photo(self) -> bool:
        return bool(self.photo_private)

    @property
    def shares_photo(self) -> bool:
        return self.photo_mode == 'exchange' and self.has_photo


class NikahInterest(models.Model):
    """«❤ Интерес» к анкете. Два встречных интереса = пара (NikahMatch)."""

    from_profile = models.ForeignKey(NikahProfile, on_delete=models.CASCADE, related_name='interests_sent')
    to_profile = models.ForeignKey(NikahProfile, on_delete=models.CASCADE, related_name='interests_received')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_profile', 'to_profile')
        ordering = ['-created_at']
        verbose_name = 'интерес'
        verbose_name_plural = 'интересы'


class NikahSkip(models.Model):
    """Свайп влево: анкета больше не показывается в ленте (вернуть — «Вернуть отклонённых»)."""

    from_profile = models.ForeignKey(NikahProfile, on_delete=models.CASCADE, related_name='skips')
    to_profile = models.ForeignKey(NikahProfile, on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ('from_profile', 'to_profile')
        verbose_name = 'пропуск анкеты'
        verbose_name_plural = 'пропуски анкет'


class NikahSaved(models.Model):
    """Закладка «сохранить анкету» — видна только владельцу."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='nikah_saved')
    profile = models.ForeignKey(NikahProfile, on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'profile')
        ordering = ['-created_at']


class NikahMatch(models.Model):
    """Взаимный интерес брата и сестры.

    Этапы: photos (обмен фото: сестра смотрит первой, у каждого — одноразовый показ
    на N минут; молчание = отказ) → chat (открыт диалог) | closed (не сложилось).
    Если хотя бы один выбрал «без фото» или фото нет — сразу chat.
    """

    PHOTOS, CHAT, CLOSED = 'photos', 'chat', 'closed'
    STAGES = [(PHOTOS, _lazy('обмен фото')), (CHAT, _lazy('чат открыт')), (CLOSED, _lazy('не сложилось'))]

    sister = models.ForeignKey(NikahProfile, on_delete=models.CASCADE, related_name='matches_as_sister')
    brother = models.ForeignKey(NikahProfile, on_delete=models.CASCADE, related_name='matches_as_brother')
    stage = models.CharField('этап', max_length=8, choices=STAGES, default=PHOTOS)
    # решения после просмотра фото: None — ещё не решил(а)
    sister_ok = models.BooleanField('сестра согласна', null=True, blank=True)
    brother_ok = models.BooleanField('брат согласен', null=True, blank=True)
    sister_viewed_at = models.DateTimeField('сестра открыла фото брата', null=True, blank=True)
    brother_viewed_at = models.DateTimeField('брат открыл фото сестры', null=True, blank=True)
    thread = models.ForeignKey('chat.Thread', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    chat_paid = models.BooleanField('чат оплачен братом', default=False)
    # фото, отправленные ботом в Telegram (защищённое сообщение) — бот удаляет их по таймеру
    sister_tg_msg = models.BigIntegerField(null=True, blank=True, editable=False)
    brother_tg_msg = models.BigIntegerField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('sister', 'brother')
        ordering = ['-created_at']
        verbose_name = 'пара'
        verbose_name_plural = 'пары (взаимный интерес)'

    def __str__(self):
        return f'{self.sister} ♥ {self.brother} — {self.get_stage_display()}'

    def side(self, profile) -> str:
        return 'sister' if profile.pk == self.sister_id else 'brother'

    def other(self, profile):
        return self.brother if profile.pk == self.sister_id else self.sister
