from django.db import models
from django.utils.translation import gettext_lazy as _lazy


class Org(models.Model):
    """Организация помощи беженцам: УВКБ ООН, посольства, Красный Полумесяц.

    Наполняет админ; данные контактов меняются часто — на странице
    всегда плашка «уточняйте актуальность».
    """

    KINDS = [
        ('intl', _lazy('Международная организация')),
        ('unhcr', _lazy('УВКБ ООН')),
        ('embassy', _lazy('Посольство')),
        ('redcrescent', _lazy('Красный Полумесяц / Красный Крест')),
        ('ngo', _lazy('Общественная организация')),
        ('lawyer', _lazy('Адвокат / юридическая помощь')),
        ('other', _lazy('Другое')),
    ]

    REGIONS = [
        ('intl', _lazy('Весь мир')),
        ('asia', _lazy('Азия')),
        ('europe', _lazy('Европа')),
        ('mideast', _lazy('Ближний Восток и Африка')),
        ('americas', _lazy('Америка')),
    ]
    # регион по стране — подставляется сам, если в админке не выбран
    REGION_BY_COUNTRY = {
        _lazy('Германия'): 'europe', _lazy('Россия'): 'europe', _lazy('Франция'): 'europe', _lazy('Великобритания'): 'europe',
        _lazy('Нидерланды'): 'europe', _lazy('Бельгия'): 'europe', _lazy('Швеция'): 'europe', _lazy('Норвегия'): 'europe',
        _lazy('Австрия'): 'europe', _lazy('Швейцария'): 'europe', _lazy('Италия'): 'europe', _lazy('Испания'): 'europe',
        _lazy('Польша'): 'europe', _lazy('Чехия'): 'europe', _lazy('Финляндия'): 'europe', _lazy('Дания'): 'europe',
        _lazy('Евросоюз'): 'europe', _lazy('Украина'): 'europe', _lazy('Грузия'): 'europe', _lazy('Армения'): 'asia',
        _lazy('Азербайджан'): 'asia', _lazy('Турция'): 'asia', _lazy('Казахстан'): 'asia', _lazy('Узбекистан'): 'asia',
        _lazy('Кыргызстан'): 'asia', _lazy('Таджикистан'): 'asia', _lazy('Туркменистан'): 'asia', _lazy('Афганистан'): 'asia',
        _lazy('Пакистан'): 'asia', _lazy('Иран'): 'asia', _lazy('Малайзия'): 'asia', _lazy('Индонезия'): 'asia',
        _lazy('Иордания'): 'mideast', _lazy('Ливан'): 'mideast', _lazy('Египет'): 'mideast', _lazy('ОАЭ'): 'mideast',
        _lazy('Саудовская Аравия'): 'mideast', _lazy('Ирак'): 'mideast', _lazy('Сирия'): 'mideast',
        _lazy('США'): 'americas', _lazy('Канада'): 'americas',
    }

    country = models.CharField('страна', max_length=80, db_index=True)
    city = models.CharField('город', max_length=80, blank=True)
    name = models.CharField('название', max_length=200)
    kind = models.CharField('тип', max_length=15, choices=KINDS, default='unhcr')
    region = models.CharField('регион', max_length=10, choices=REGIONS, blank=True, db_index=True,
                              help_text='Пусто — определится по стране')
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

    def save(self, *args, **kwargs):
        if not self.region:
            self.region = 'intl' if self.kind == 'intl' else self.REGION_BY_COUNTRY.get(self.country, '')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.country})'

    def phone_list(self):
        """Телефоны списком для кнопок звонка."""
        return [p.strip() for p in self.phones.split(',') if p.strip()]
