from django.db import models

from apps.maps.models import BasePlace


class Doctor(BasePlace):
    """Врач на карте платформы (ПАССПОРТ §2 «Здоровье»).

    Платформа не ставит диагнозы: врач публикует себя и контакты,
    консультация — напрямую. Публикация может быть платной (настройка админа).
    """

    SPECIALIZATIONS = [
        ('gp', 'Терапевт / семейный'), ('cardio', 'Кардиолог'),
        ('neuro', 'Невролог'), ('pediatr', 'Педиатр'),
        ('dentist', 'Стоматолог'), ('gyneco', 'Гинеколог'),
        ('psych', 'Психолог / психотерапевт'), ('other', 'Другое'),
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
