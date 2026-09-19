from django.db import models


class Org(models.Model):
    """Организация помощи беженцам: УВКБ ООН, посольства, Красный Полумесяц.

    Наполняет админ; данные контактов меняются часто — на странице
    всегда плашка «уточняйте актуальность».
    """

    KINDS = [
        ('unhcr', 'УВКБ ООН'),
        ('embassy', 'Посольство'),
        ('redcrescent', 'Красный Полумесяц / Красный Крест'),
        ('ngo', 'Общественная организация'),
        ('other', 'Другое'),
    ]

    country = models.CharField('страна', max_length=80, db_index=True)
    city = models.CharField('город', max_length=80, blank=True)
    name = models.CharField('название', max_length=200)
    kind = models.CharField('тип', max_length=15, choices=KINDS, default='unhcr')
    phones = models.CharField('телефоны (через запятую)', max_length=300, blank=True,
                              help_text='Например: +90 312 000 00 00, +90 312 000 00 01')
    address = models.CharField('адрес', max_length=300, blank=True)
    website = models.URLField('сайт', blank=True)
    notes = models.TextField('примечания', blank=True,
                             help_text='Часы работы, условия приёма, на что обратить внимание')
    updated_at = models.DateTimeField('обновлено', auto_now=True)

    class Meta:
        ordering = ['country', 'name']
        verbose_name = 'организация'
        verbose_name_plural = 'организации помощи беженцам'

    def __str__(self):
        return f'{self.name} ({self.country})'

    def phone_list(self):
        """Телефоны списком для кнопок звонка."""
        return [p.strip() for p in self.phones.split(',') if p.strip()]
