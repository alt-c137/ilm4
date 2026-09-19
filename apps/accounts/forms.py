"""Формы входа, регистрации (гибкие поля) и профиля."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import RegistrationField

User = get_user_model()


class LoginForm(forms.Form):
    login = forms.CharField(label='Email или логин', max_length=254)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user_cache = None

    def clean(self):
        from django.contrib.auth import authenticate

        cleaned = super().clean()
        login_value = cleaned.get('login')
        password = cleaned.get('password')
        if login_value and password:
            self.user_cache = authenticate(self.request, username=login_value, password=password)
            if self.user_cache is None:
                raise forms.ValidationError('Неверный email/логин или пароль.')
        return cleaned

    def get_user(self):
        return self.user_cache


class RegisterForm(forms.Form):
    """Email + пароль всегда; остальные поля — из RegistrationField (админка)."""

    email = forms.EmailField(label='Email')
    username = forms.CharField(label='Логин', max_length=150, help_text='Можно оставить пустым — сгенерируем из email', required=False)
    password1 = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Пароль ещё раз', widget=forms.PasswordInput)

    FIELD_WIDGETS = {  # как строить доп-поля по ключам RegistrationField
        'nickname': forms.CharField(label='Ник', max_length=40, required=False),
        'city': forms.CharField(label='Город', max_length=80, required=False),
        'first_name': forms.CharField(label='Имя', max_length=150, required=False),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # поля регистрации, включённые админом
        self.extra_fields = []
        for rf in (RegistrationField.objects.filter(enabled=True)
                   .order_by('order', 'id')):
            if rf.key in self.FIELD_WIDGETS:
                field = self.FIELD_WIDGETS[rf.key]
                field.label = rf.label
                field.required = rf.required
                self.fields[rf.key] = field
                self.extra_fields.append(rf.key)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Этот email уже зарегистрирован.')
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            return username  # сгенерируем при сохранении
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Этот логин занят.')
        return username

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Пароли не совпадают.')
        elif p1:
            validate_password(p1)
        return cleaned

    def save(self):
        data = self.cleaned_data
        username = data.get('username') or data['email'].split('@')[0]
        if User.objects.filter(username=username).exists():
            username = f'{username}{User.objects.count() + 1}'
        extra = {key: data.get(key, '') for key in self.extra_fields}
        return User.objects.create_user(
            username=username,
            email=data['email'],
            password=data['password1'],
            first_name=extra.get('first_name', ''),
            nickname=extra.get('nickname', ''),
            city=extra.get('city', ''),
        )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['nickname', 'first_name', 'city', 'avatar']
        labels = {
            'nickname': 'Ник', 'first_name': 'Имя', 'city': 'Город',
            'avatar': 'Аватар',
        }
        widgets = {
            # аву меняем кликом по фото в карточке — стандартная кнопка не нужна
            'avatar': forms.ClearableFileInput(attrs={'data-skip': '1'}),
        }
