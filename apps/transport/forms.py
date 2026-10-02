from django import forms

from .models import Ride, Trip


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


class TripForm(forms.ModelForm):
    """Попутчики. Валюта по умолчанию подставляется по человеку (views / API)."""

    class Meta:
        model = Trip
        fields = ['role', 'from_city', 'to_city', 'via', 'departs_at', 'car', 'seats', 'front_seat', 'price',
                  'currency', 'audience', 'parcels', 'comment']
        labels = {
            'role': 'Кто вы', 'from_city': 'Откуда', 'to_city': 'Куда', 'via': 'По пути (через)',
            'departs_at': 'Дата и время выезда', 'car': 'Машина', 'seats': 'Мест',
            'front_seat': 'Переднее место свободно', 'price': 'Цена за место', 'currency': 'Валюта',
            'audience': 'Кого беру', 'parcels': 'Возьму посылку', 'comment': 'Комментарий',
        }
        widgets = {
            'departs_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'comment': forms.Textarea(attrs={'rows': 3}),
            'seats': forms.NumberInput(attrs={'min': 1, 'max': 8}),
            'price': forms.NumberInput(attrs={'min': 0}),
        }

    # часовой пояс устройства автора (минут от UTC) — проставляет страница / приложение
    tz_offset = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['departs_at'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M']
        if self.instance.pk:                           # правка: показываем время «как на часах» в городе выезда
            self.initial['departs_at'] = self.instance.departs_local
            self.initial['tz_offset'] = self.instance.tz_offset

    def clean_seats(self):
        from django.utils.translation import gettext as _
        n = self.cleaned_data['seats']
        if not 1 <= n <= 8:
            raise forms.ValidationError(_('От 1 до 8 мест.'))
        return n

    def clean(self):
        from datetime import timedelta
        from datetime import timezone as dt_tz

        from django.utils import timezone
        from django.utils.translation import gettext as _
        data = super().clean()
        if data.get('from_city') and data.get('to_city') and data['from_city'].strip().lower() == data['to_city'].strip().lower():
            self.add_error('to_city', _('Откуда и куда совпадают.'))
        when, offset = data.get('departs_at'), data.get('tz_offset')
        if when:
            if offset is not None and -720 <= offset <= 840:
                # человек ввёл время по своим часам: переводим в точный момент
                when = timezone.make_naive(when).replace(tzinfo=dt_tz(timedelta(minutes=offset)))
            else:
                offset = None
            now = timezone.now()
            if when < now - timedelta(minutes=30):
                self.add_error('departs_at', _('Время выезда уже прошло.'))
            elif when > now + timedelta(days=120):
                self.add_error('departs_at', _('Слишком далёкая дата — укажите поездку в ближайшие месяцы.'))
            data['departs_at'], data['tz_offset'] = when, offset
        return data

    def save(self, commit=True):
        self.instance.tz_offset = self.cleaned_data.get('tz_offset')
        return super().save(commit)
