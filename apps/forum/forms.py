from django import forms

from .models import Reply, Topic


class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ['title', 'body']
        labels = {'title': 'Вопрос', 'body': 'Подробности'}
        widgets = {'body': forms.Textarea(attrs={'rows': 4})}


class ReplyForm(forms.ModelForm):
    class Meta:
        model = Reply
        fields = ['body']
        labels = {'body': 'Ваш ответ'}
        widgets = {'body': forms.Textarea(attrs={'rows': 3})}
