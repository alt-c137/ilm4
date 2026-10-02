"""Формы входа, регистрации (гибкие поля) и профиля."""
import copy

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from .models import RegistrationField

User = get_user_model()


class LoginForm(forms.Form):
    login = forms.CharField(label=_lazy('Email или логин'), max_length=254)
    password = forms.CharField(label=_lazy('Пароль'), widget=forms.PasswordInput)

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
                raise forms.ValidationError(_('Неверный email/логин или пароль.'))
        return cleaned

    def get_user(self):
        return self.user_cache


class RegisterForm(forms.Form):
    """Email + пароль всегда; остальные поля — из RegistrationField (админка)."""

    email = forms.EmailField(label='Email')
    username = forms.CharField(label=_lazy('Логин'), max_length=150, help_text='Можно оставить пустым — сгенерируем из email', required=False)
    password1 = forms.CharField(label=_lazy('Пароль'), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_lazy('Пароль ещё раз'), widget=forms.PasswordInput)

    FIELD_WIDGETS = {  # как строить доп-поля по ключам RegistrationField
        'nickname': forms.CharField(label=_lazy('Ник'), max_length=40, required=False),
        'city': forms.CharField(label=_lazy('Город'), max_length=80, required=False),
        'first_name': forms.CharField(label=_lazy('Имя'), max_length=150, required=False),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # поля регистрации, включённые админом
        self.extra_fields = []
        for rf in (RegistrationField.objects.filter(enabled=True)
                   .order_by('order', 'id')):
            if rf.key in self.FIELD_WIDGETS:
                field = copy.deepcopy(self.FIELD_WIDGETS[rf.key])   # общий шаблон не портим
                field.label = rf.label
                field.required = rf.required
                self.fields[rf.key] = field
                self.extra_fields.append(rf.key)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_('Этот email уже зарегистрирован.'))
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            return username  # сгенерируем при сохранении
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(_('Этот логин занят.'))
        return username

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', _('Пароли не совпадают.'))
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
        fields = ['first_name', 'last_name', 'handle', 'bio', 'city', 'avatar', 'phone', 'findable_by_phone',
                  'phone_privacy', 'seen_privacy']
        labels = {
            'first_name': 'Имя', 'last_name': 'Фамилия', 'city': 'Город',
            'avatar': 'Аватар', 'phone': 'Телефон', 'handle': 'Имя пользователя', 'bio': 'О себе',
            'findable_by_phone': 'Меня можно найти по номеру телефона',
            'phone_privacy': 'Кто видит мой номер', 'seen_privacy': 'Кто видит, когда я в сети',
        }
        widgets = {
            # аву меняем кликом по фото в карточке — стандартная кнопка не нужна
            'avatar': forms.FileInput(attrs={'data-skip': '1', 'hidden': True, 'accept': 'image/*'}),
            'phone': forms.TextInput(attrs={'placeholder': '+998 90 123 45 67', 'inputmode': 'tel',
                                            'autocomplete': 'tel'}),
            'handle': forms.TextInput(attrs={'placeholder': 'ali_2024', 'autocapitalize': 'none', 'autocomplete': 'off',
                                             'spellcheck': 'false', 'maxlength': 32}),
            'bio': forms.TextInput(attrs={'maxlength': 160}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('phone_privacy', 'seen_privacy'):       # не пришло в форме — остаётся как было
            self.fields[name].required = False
        # раньше вместо имени был «ник»: показываем его в поле «Имя», после сохранения ник больше не нужен
        if not self.is_bound and not self.instance.first_name and self.instance.nickname:
            self.initial['first_name'] = self.instance.nickname

    def clean_phone_privacy(self):
        return self.cleaned_data.get('phone_privacy') or self.instance.phone_privacy

    def clean_seen_privacy(self):
        return self.cleaned_data.get('seen_privacy') or self.instance.seen_privacy

    def clean_handle(self):
        from . import people
        try:
            return people.clean_handle(self.cleaned_data.get('handle'), user=self.instance)
        except people.PeopleError as exc:
            raise forms.ValidationError(exc.message) from exc

    def save(self, commit=True):
        from .phones import phone_key
        if self.cleaned_data.get('first_name'):
            self.instance.nickname = ''
        if 'phone' in self.changed_data and phone_key(self.initial.get('phone') or '') != phone_key(
                self.cleaned_data.get('phone') or ''):
            self.instance.phone_verified_at = None        # номер другой — подтверждать заново (иначе «галочка» досталась бы чужому номеру)
        return super().save(commit)

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and hasattr(avatar, 'size') and avatar.size > 5 * 1024 * 1024:
            raise forms.ValidationError(_('Фото больше 5 МБ'))
        return avatar
