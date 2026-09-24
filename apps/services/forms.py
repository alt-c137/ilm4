from django import forms

from .models import Service


class ServiceForm(forms.ModelForm):
    """Услуга / фриланс (правка своей публикации)."""

    class Meta:
        model = Service
        fields = ['name', 'kind', 'city', 'description', 'price_text', 'contact']
        labels = {'name': 'Название', 'kind': 'Вид', 'city': 'Город', 'description': 'Описание',
                  'price_text': 'Цена', 'contact': 'Контакт'}
        widgets = {'description': forms.Textarea(attrs={'rows': 5})}
