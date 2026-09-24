from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _lazy

from apps.core.models import Moderation


class Vacancy(models.Model):
    """Вакансия. Публикуется после модерации."""

    CATEGORIES = [
        ('it', _lazy('IT и интернет')), ('drive', _lazy('Вождение и доставка')),
        ('build', _lazy('Строительство')), ('med', _lazy('Медицина')),
        ('edu', _lazy('Образование')), ('trade', _lazy('Торговля')), ('other', _lazy('Другое')),
    ]

    VACANCY, RESUME = 'vacancy', 'resume'
    KINDS = [(VACANCY, _lazy('Вакансия — ищу работника')), (RESUME, _lazy('Резюме — ищу работу'))]

    kind = models.CharField('тип', max_length=8, choices=KINDS, default=VACANCY, db_index=True)
    title = models.CharField('должность', max_length=160)
    category = models.CharField('раздел', max_length=20, choices=CATEGORIES,
                                default='other')
    company = models.CharField('компания', max_length=160, blank=True,
                               help_text='Для вакансии. В резюме можно оставить пустым')
    city = models.CharField('город', max_length=80)
    salary = models.CharField('зарплата', max_length=80, blank=True,
                              help_text='Например: 5 000 000 сум или договорная')
    description = models.TextField('описание')
    contact = models.CharField('контакт', max_length=120)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='vacancies')
    status = models.CharField('статус', max_length=10, choices=Moderation.CHOICES,
                              default=Moderation.PENDING)
    created_at = models.DateTimeField('создано', auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'вакансия'
        verbose_name_plural = 'вакансии'

    def __str__(self):
        return f'{self.title} — {self.company or self.get_kind_display()}'

    @property
    def is_resume(self) -> bool:
        return self.kind == self.RESUME


class VacancyResponse(models.Model):
    """Отклик: виден только автору вакансии."""

    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='responses')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='vacancy_responses')
    message = models.TextField('сопроводительное сообщение')
    created_at = models.DateTimeField('создано', auto_now_add=True)

    class Meta:
        verbose_name = 'отклик'
        verbose_name_plural = 'отклики'
