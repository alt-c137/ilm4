from django import forms

from .models import Vacancy, VacancyResponse


class VacancyForm(forms.ModelForm):
    class Meta:
        model = Vacancy
        fields = ['title', 'company', 'city', 'salary', 'description', 'contact']
        widgets = {'description': forms.Textarea(attrs={'rows': 5})}


class VacancyResponseForm(forms.ModelForm):
    class Meta:
        model = VacancyResponse
        fields = ['message']
        labels = {'message': 'Сообщение работодателю'}
        widgets = {'message': forms.Textarea(attrs={'rows': 4})}
