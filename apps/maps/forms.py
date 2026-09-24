from django import forms
from django.utils.translation import gettext as _

from .models import HalalPlace


class HalalPlaceForm(forms.ModelForm):
    """Добавление халяль-места участником (попадает на модерацию)."""

    class Meta:
        model = HalalPlace
        fields = ['name', 'category', 'city', 'address', 'lat', 'lon',
                  'phone', 'url', 'description', 'photo',
                  # мечеть (показываются при категории «Мечеть»)
                  'branch', 'madhhab', 'manhaj', 'kind', 'affiliation', 'imam', 'khutba_lang',
                  'has_jumua', 'has_women', 'has_wudu', 'has_parking', 'accessible']
        labels = {
            'name': 'Название', 'category': 'Категория', 'city': 'Город',
            'address': 'Адрес', 'lat': 'Широта', 'lon': 'Долгота',
            'phone': 'Телефон', 'url': 'Сайт или соцсеть',
            'description': 'Описание', 'photo': 'Фото',
        }
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'category' in self.fields:
            self.fields['category'].choices = [('', _('— выберите из списка —'))] + [c for c in self.fields['category'].choices if c[0] != '']
