"""Трекер привычек и дел: «сегодня выпить таблетки, выучить 10 слов, прочитать 5 страниц».

Свои привычки видит только сам человек. Общий трекер (Board) ведут вместе: семья, напарники
по работе, группа, которая учит арабский. У каждого участника свои отметки; по желанию владельца
включается соревнование — таблица, кто сколько выполнил.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _lazy


class Board(models.Model):
    """Общий трекер: привычки одни на всех, отметки — у каждого свои."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tracker_boards_owned')
    title = models.CharField('название', max_length=80)
    emoji = models.CharField('значок', max_length=16, default='h-together')   # ключ значка из набора (hicon); раньше — эмодзи
    compete = models.BooleanField('соревнование', default=False,
                                  help_text='Таблица: кто сколько выполнил. Выключено — просто общий список')
    invite_code = models.CharField('код приглашения', max_length=24, unique=True)
    ends_on = models.DateField('соревнование до', null=True, blank=True,
                               help_text='Пусто — без срока. С датой — после неё видно победителя')
    thread = models.ForeignKey('chat.Thread', null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
                               verbose_name='чат трекера')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through='BoardMember', related_name='tracker_boards')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'общий трекер'
        verbose_name_plural = 'общие трекеры'

    def __str__(self):
        return self.title


class BoardMember(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tracker_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['board', 'user'], name='one_tracker_membership')]
        verbose_name = 'участник общего трекера'
        verbose_name_plural = 'участники общих трекеров'


class Habit(models.Model):
    """Привычка (повторяется по дням недели) или разовое дело на конкретный день."""

    CHECK, COUNT = 'check', 'count'
    KINDS = [(CHECK, _lazy('Сделал / не сделал')), (COUNT, _lazy('Количество (стаканы, страницы, минуты)'))]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='habits')
    board = models.ForeignKey(Board, null=True, blank=True, on_delete=models.CASCADE, related_name='habits',
                              verbose_name='общий трекер', help_text='Пусто — личная привычка')
    title = models.CharField('что делать', max_length=80)
    emoji = models.CharField('значок', max_length=16, default='h-check')      # ключ значка из набора (hicon); раньше — эмодзи
    color = models.CharField('цвет', max_length=7, default='#6d5efc')
    kind = models.CharField('вид', max_length=5, choices=KINDS, default=CHECK)
    target = models.PositiveIntegerField('цель в день', default=1)
    unit = models.CharField('единица (стаканов, страниц…)', max_length=16, blank=True)
    days = models.CharField('дни недели', max_length=7, default='1234567',
                            help_text='1 — понедельник … 7 — воскресенье')
    once_on = models.DateField('разовое дело — на этот день', null=True, blank=True)
    remind_at = models.TimeField('напомнить в', null=True, blank=True)
    tz_offset = models.SmallIntegerField('часовой пояс автора, минут от UTC', default=300)
    archived = models.BooleanField('в архиве', default=False)
    order = models.PositiveSmallIntegerField(default=0)
    # --- v49: время дня, «N раз в неделю», несколько напоминаний, заметка (дозировка, «после еды») ---
    PARTS = [('', _lazy('В любое время')), ('morning', _lazy('Утро')), ('day', _lazy('День')), ('evening', _lazy('Вечер'))]
    part = models.CharField('время дня', max_length=8, choices=PARTS, blank=True, default='')
    per_week = models.PositiveSmallIntegerField('раз в неделю', default=0,
                                                help_text='0 — по дням недели; 1–6 — столько раз в неделю, в любые дни')
    reminders = models.CharField('напоминания', max_length=60, blank=True, help_text='Через запятую: 08:00,14:00,20:00')
    note = models.CharField('заметка', max_length=200, blank=True, help_text='Например: «1 таблетка после еды»')
    created_at = models.DateTimeField(auto_now_add=True)
    start_on = models.DateField('с какого дня', null=True, blank=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'привычка / дело'
        verbose_name_plural = 'привычки и дела'

    def __str__(self):
        return self.title

    def due_on(self, day) -> bool:
        """Нужно ли это делать в такой день."""
        if self.once_on:
            return self.once_on == day
        if self.start_on and day < self.start_on:
            return False
        if self.per_week:
            return True                       # «3 раза в неделю» — в любой день, пока недельная цель не выполнена
        return str(day.isoweekday()) in self.days

    def times(self) -> list:
        """Все времена напоминаний ['08:00', '20:00']."""
        out = [t for t in (self.reminders or '').split(',') if t]
        if self.remind_at:
            first = self.remind_at.strftime('%H:%M')
            if first not in out:
                out.insert(0, first)
        return out


class HabitLog(models.Model):
    """Отметка за день: сколько сделано (для «сделал / не сделал» — 1)."""

    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name='logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='habit_logs')
    day = models.DateField('день')
    value = models.PositiveIntegerField('сделано', default=0)
    skipped = models.BooleanField('пропуск по уважительной причине', default=False,
                                  help_text='Болезнь, дорога — день не считается и серию не рвёт')
    note = models.CharField('заметка', max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['habit', 'user', 'day'], name='one_log_per_day')]
        indexes = [models.Index(fields=['user', 'day'])]
        verbose_name = 'отметка'
        verbose_name_plural = 'отметки'
