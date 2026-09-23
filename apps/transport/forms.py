from django import forms

from .models import Ride


class RideForm(forms.ModelForm):
    class Meta:
        model = Ride
        fields = ['type', 'company', 'from_city', 'to_city', 'ride_date', 'price_text',
                  'description', 'contact']
        labels = {
            'type': 'Тип перевозки', 'company': 'Перевозчик / компания', 'from_city': 'Откуда', 'to_city': 'Куда',
            'ride_date': 'Дата поездки (если разовая)',
            'price_text': 'Цена (текстом)', 'description': 'Описание',
            'contact': 'Контакт',
        }
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}
