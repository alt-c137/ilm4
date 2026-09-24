from django.db import models
from django.utils.translation import gettext_lazy as _lazy

from apps.maps.models import BasePlace


class Doctor(BasePlace):
    """Врач на карте платформы (ПАССПОРТ §2 «Здоровье»).

    Платформа не ставит диагнозы: врач публикует себя и контакты,
    консультация — напрямую. Публикация может быть платной (настройка админа).
    """

    SPECIALIZATIONS = [
        ('gp', _lazy('Терапевт / семейный')), ('cardio', _lazy('Кардиолог')),
        ('neuro', _lazy('Невролог')), ('pediatr', _lazy('Педиатр')),
        ('dentist', _lazy('Стоматолог')), ('gyneco', _lazy('Гинеколог')),
        ('psych', _lazy('Психолог / психотерапевт')), ('hijama', _lazy('Хиджама')), ('other', _lazy('Другое')),
    ]

    category = models.CharField('специализация', max_length=30, choices=SPECIALIZATIONS)
    experience = models.PositiveSmallIntegerField('опыт, лет', default=0)
    clinic = models.CharField('клиника/кабинет', max_length=160, blank=True)

    class Meta(BasePlace.Meta):
        verbose_name = 'врач'
        verbose_name_plural = 'врачи'

    @property
    def specialization(self):
        return self.get_category_display()
