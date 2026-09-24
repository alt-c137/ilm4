"""Анкета никяха: одна форма на весь мастер (15 шагов показывает JS, проверяет сервер)."""
from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from . import choices as C
from .models import NikahProfile
from .services import has_contacts

TEXT_MAX = 900
CONTACTS_ERROR = _lazy('Уберите контакты (телефон, ссылки, ники, соцсети) — общение только внутри сервиса.')

# на каком шаге мастера поле — чтобы вернуть человека к ошибке
STEP_OF = {
    'gender': 1, 'name': 2, 'age': 2, 'age_from': 2, 'age_to': 2,
    'country': 3, 'city': 3, 'nationality': 3, 'height': 4, 'weight': 4,
    'marital': 5, 'wife_number': 5, 'polygyny': 5,
    'madhhab': 6, 'aqida': 6, 'prayer': 6, 'quran': 6, 'where_allah': 6,
    'has_children': 7, 'children_want': 7, 'children_accept': 7, 'ready_when': 7, 'look': 8, 'manhaj_text': 9,
    'relocation': 10, 'about': 11, 'partner_expectations': 12, 'photo_mode': 13,
}


class NikahProfileForm(forms.ModelForm):
    class Meta:
        model = NikahProfile
        fields = list(STEP_OF)

    REQUIRED = ['gender', 'name', 'age', 'country', 'marital', 'madhhab', 'aqida', 'prayer', 'quran',
                'where_allah', 'has_children', 'children_want', 'children_accept', 'ready_when', 'look', 'manhaj_text',
                'relocation', 'about', 'partner_expectations', 'photo_mode']

    def __init__(self, *args, editing=False, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.REQUIRED:
            self.fields[name].required = True
        if editing:                        # пол не меняется после создания анкеты
            self.fields['gender'].disabled = True

    def clean_age(self):
        age = self.cleaned_data['age']
        if not 18 <= age <= 80:
            raise forms.ValidationError(_('Возраст — от 18 до 80 лет'))
        return age

    def _range(self, name, lo, hi, what):
        value = self.cleaned_data.get(name)
        if value is not None and not lo <= value <= hi:
            raise forms.ValidationError(_('{what}: от {lo} до {hi}').format(what=what, lo=lo, hi=hi))
        return value

    def clean_height(self):
        return self._range('height', 120, 230, _('Рост'))

    def clean_weight(self):
        return self._range('weight', 40, 200, _('Вес'))

    def _text(self, name, minimum):
        text = (self.cleaned_data.get(name) or '').strip()
        if len(text) < minimum:
            raise forms.ValidationError(_('Напишите хотя бы {minimum} символов').format(minimum=minimum))
        if len(text) > TEXT_MAX:
            raise forms.ValidationError(_('Не больше {TEXT_MAX} символов').format(TEXT_MAX=TEXT_MAX))
        if has_contacts(text):
            raise forms.ValidationError(CONTACTS_ERROR)
        return text

    def clean_manhaj_text(self):
        return self._text('manhaj_text', 10)

    def clean_about(self):
        return self._text('about', 20)

    def clean_partner_expectations(self):
        return self._text('partner_expectations', 20)

    def clean_country(self):
        from .geo import canonical_country
        return canonical_country(self.cleaned_data.get('country', ''))

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if has_contacts(name):
            raise forms.ValidationError(CONTACTS_ERROR)
        return name

    def clean(self):
        data = super().clean()
        gender = data.get('gender') or (self.instance.gender if self.instance.pk else '')
        lo, hi = data.get('age_from'), data.get('age_to')
        if lo is not None and hi is not None and not (18 <= lo <= hi <= 80):
            self.add_error('age_to', _('Диапазон возраста: от 18 до 80, «от» не больше «до»'))
        if gender == 'M':
            data['polygyny'] = ''
            if data.get('marital') == 'married' and (data.get('wife_number') or 1) < 2:
                self.add_error('wife_number', _('Вы женаты — укажите, какую по счёту жену ищете (2–4)'))
            if not data.get('wife_number'):
                data['wife_number'] = 1
            if data.get('look') not in dict(C.LOOK_M):
                self.add_error('look', _('Выберите вариант'))
        elif gender == 'F':
            data['wife_number'] = None
            if data.get('marital') == 'married':
                self.add_error('marital', _('Выберите вариант'))
            if not data.get('polygyny'):
                self.add_error('polygyny', _('Выберите вариант'))
            if data.get('look') not in dict(C.LOOK_F):
                self.add_error('look', _('Выберите вариант'))
        return data

    def first_error_step(self) -> int:
        steps = [STEP_OF.get(name, 1) for name in self.errors]
        return min(steps) if steps else 1
