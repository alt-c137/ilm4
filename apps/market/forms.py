from django import forms

from .models import Listing

MAX_PHOTO_MB = 10


class ListingForm(forms.ModelForm):
    """Создание объявления. Одно фото (несколько — фаза позже)."""

    class Meta:
        model = Listing
        fields = ['title', 'description', 'price', 'currency', 'category',
                  'city', 'contact', 'photo']
        labels = {
            'title': 'Заголовок', 'description': 'Описание', 'price': 'Цена',
            'currency': 'Валюта', 'category': 'Категория', 'city': 'Город',
            'contact': 'Контакт', 'photo': 'Фото',
        }
        widgets = {'description': forms.Textarea(attrs={'rows': 5})}

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and photo.size > MAX_PHOTO_MB * 1024 * 1024:
            raise forms.ValidationError(f'Фото больше {MAX_PHOTO_MB} МБ')
        return photo

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise forms.ValidationError('Цена не может быть отрицательной')
        return price
