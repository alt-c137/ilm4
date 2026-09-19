from django import forms

from .models import HalalPlace


class HalalPlaceForm(forms.ModelForm):
    """Добавление халяль-места участником (попадает на модерацию)."""

    class Meta:
        model = HalalPlace
        fields = ['name', 'category', 'city', 'address', 'lat', 'lon',
                  'phone', 'url', 'description', 'photo']
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
            self.fields['category'].choices = [(chr(39)+chr(39), '— выберите из списка —')] + list(self.fields['category'].choices)
