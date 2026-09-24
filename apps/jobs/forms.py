from django import forms

from .models import Vacancy, VacancyResponse


class VacancyForm(forms.ModelForm):
    class Meta:
        model = Vacancy
        fields = ['kind', 'title', 'category', 'company', 'city', 'salary', 'description', 'contact']
        widgets = {'description': forms.Textarea(attrs={'rows': 5}), 'kind': forms.RadioSelect}
        labels = {'kind': 'Что публикуете', 'category': 'Раздел', 'title': 'Должность', 'company': 'Компания',
                  'city': 'Город', 'salary': 'Зарплата / ожидания', 'description': 'Описание',
                  'contact': 'Контакт'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kind'].required = False

    def clean_kind(self):
        return self.cleaned_data.get('kind') or Vacancy.VACANCY

    def clean(self):
        data = super().clean()
        if data.get('kind') == Vacancy.VACANCY and not (data.get('company') or '').strip():
            self.add_error('company', 'Укажите компанию или «Частное лицо»')
        return data


class VacancyResponseForm(forms.ModelForm):
    class Meta:
        model = VacancyResponse
        fields = ['message']
        labels = {'message': 'Сообщение работодателю'}
        widgets = {'message': forms.Textarea(attrs={'rows': 4})}
