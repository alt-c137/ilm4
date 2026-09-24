from django import forms
from django.utils.translation import gettext as _

from .models import Doctor


class DoctorForm(forms.ModelForm):
    """Врач публикует себя (или админ за него). Публикация может быть платной."""

    class Meta:
        model = Doctor
        fields = ['name', 'category', 'city', 'clinic', 'experience', 'address',
                  'lat', 'lon', 'phone', 'url', 'description', 'photo']
        labels = {
            'name': 'Имя врача', 'category': 'Специализация', 'city': 'Город',
            'clinic': 'Клиника / кабинет', 'experience': 'Опыт (лет)',
            'address': 'Адрес', 'lat': 'Широта', 'lon': 'Долгота',
            'phone': 'Телефон', 'url': 'Сайт или соцсеть',
            'description': 'О себе', 'photo': 'Фото',
        }
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'category' in self.fields:
            self.fields['category'].choices = [('', _('— выберите из списка —'))] + [c for c in self.fields['category'].choices if c[0] != '']
