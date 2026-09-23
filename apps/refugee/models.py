from django.db import models


class Org(models.Model):
    """Организация помощи беженцам: УВКБ ООН, посольства, Красный Полумесяц.

    Наполняет админ; данные контактов меняются часто — на странице
    всегда плашка «уточняйте актуальность».
    """

    KINDS = [
        ('intl', 'Международная организация'),
        ('unhcr', 'УВКБ ООН'),
        ('embassy', 'Посольство'),
        ('redcrescent', 'Красный Полумесяц / Красный Крест'),
        ('ngo', 'Общественная организация'),
        ('lawyer', 'Адвокат / юридическая помощь'),
        ('other', 'Другое'),
    ]

    REGIONS = [
        ('intl', 'Весь мир'),
        ('asia', 'Азия'),
        ('europe', 'Европа'),
        ('mideast', 'Ближний Восток и Африка'),
        ('americas', 'Америка'),
    ]
    # регион по стране — подставляется сам, если в админке не выбран
    REGION_BY_COUNTRY = {
        'Германия': 'europe', 'Россия': 'europe', 'Франция': 'europe', 'Великобритания': 'europe',
        'Нидерланды': 'europe', 'Бельгия': 'europe', 'Швеция': 'europe', 'Норвегия': 'europe',
        'Австрия': 'europe', 'Швейцария': 'europe', 'Италия': 'europe', 'Испания': 'europe',
        'Польша': 'europe', 'Чехия': 'europe', 'Финляндия': 'europe', 'Дания': 'europe',
        'Евросоюз': 'europe', 'Украина': 'europe', 'Грузия': 'europe', 'Армения': 'asia',
        'Азербайджан': 'asia', 'Турция': 'asia', 'Казахстан': 'asia', 'Узбекистан': 'asia',
        'Кыргызстан': 'asia', 'Таджикистан': 'asia', 'Туркменистан': 'asia', 'Афганистан': 'asia',
        'Пакистан': 'asia', 'Иран': 'asia', 'Малайзия': 'asia', 'Индонезия': 'asia',
        'Иордания': 'mideast', 'Ливан': 'mideast', 'Египет': 'mideast', 'ОАЭ': 'mideast',
        'Саудовская Аравия': 'mideast', 'Ирак': 'mideast', 'Сирия': 'mideast',
        'США': 'americas', 'Канада': 'americas',
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
