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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'category' in self.fields:
            self.fields['category'].empty_label = '— выберите из списка —'
        placeholders = {
            'title': 'Например: iPhone 14 Pro, 128 ГБ',
            'description': 'Состояние, комплект, причина продажи — чем подробнее, тем быстрее продастся',
            'city': 'Ташкент',
            'contact': 'Телефон или Telegram — необязательно',
        }
        for name, text in placeholders.items():
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault('placeholder', text)
        if 'price' in self.fields:
            self.fields['price'].widget.attrs.update({'inputmode': 'decimal', 'min': '0'})
