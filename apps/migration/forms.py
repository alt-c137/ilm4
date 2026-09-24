from django import forms

from .models import Story


class StoryForm(forms.ModelForm):
    """История переезда (правка своей публикации)."""

    class Meta:
        model = Story
        fields = ['title', 'country_from', 'country_to', 'body']
        labels = {'title': 'Заголовок', 'country_from': 'Откуда', 'country_to': 'Куда', 'body': 'История'}
        widgets = {'body': forms.Textarea(attrs={'rows': 8})}
