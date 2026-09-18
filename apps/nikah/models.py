from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import Moderation


class NikahProfile(models.Model):
    """Анкета для знакомства с целью брака.

    Просмотр анкет бесплатный; «написать» платно для мужчин (PASSPORT §2),
    женщинам — бесплатно. Решение о цене — настройка админа.
    """

    GENDERS = [('M', 'Брат'), ('F', 'Сестра')]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='nikah_profile')
    gender = models.CharField('кто', max_length=1, choices=GENDERS)
    age = models.PositiveSmallIntegerField('возраст')
    city = models.CharField('город', max_length=80)
    about = models.TextField('о себе')
    partner_expectations = models.TextField('кого ищете', blank=True)
    photo = models.ImageField('фото', upload_to='nikah/%Y/%m/', blank=True, null=True)
    contact_hint = models.CharField('как связаться (показывается после оплаты)',
                                    max_length=200, blank=True,
                                    help_text='Например: telegram @ник или email')
    status = models.CharField('статус', max_length=10, choices=Moderation.CHOICES,
                              default=Moderation.PENDING)
    is_active = models.BooleanField('анкета активна', default=True)
    boosted_until = models.DateTimeField('буст до', null=True, blank=True)
    created_at = models.DateTimeField('создано', auto_now_add=True)

    class Meta:
        ordering = ['-boosted_until', '-created_at']
        verbose_name = 'анкета никаха'
        verbose_name_plural = 'анкеты никаха'

    def __str__(self):
        return f'{self.get_gender_display()}, {self.age}, {self.city}'

    @property
    def is_boosted(self) -> bool:
        return self.boosted_until and self.boosted_until > timezone.now()


class NikahContact(models.Model):
    """Оплаченное разрешение «написать» (один раз на пару анкет)."""

    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='nikah_contacts_made')
    to_profile = models.ForeignKey(NikahProfile, on_delete=models.CASCADE,
                                   related_name='contacts_received')
    created_at = models.DateTimeField('оплачено', auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_profile')
        verbose_name = 'контакт никаха'
        verbose_name_plural = 'контакты никаха'
