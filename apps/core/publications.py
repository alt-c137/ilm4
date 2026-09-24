"""Реестр пользовательских публикаций: «Мои публикации» (правка, скрытие, удаление),
уведомления автору о модерации и жалобы — одной механикой для всех разделов.

Новый раздел с публикациями = одна строка в PUBLICATIONS.
"""
from dataclasses import dataclass
from importlib import import_module

from django.apps import apps
from django.urls import reverse


@dataclass(frozen=True)
class Pub:
    key: str             # короткий ключ в адресе: /my/<key>/<pk>/
    label: str           # «Вакансии»
    model: str           # 'jobs.Vacancy'
    owner: str = 'owner'
    title: str = 'title'
    url: str = ''        # имя маршрута детальной страницы (pk) или адрес списка
    form: str = ''       # 'apps.jobs.forms.VacancyForm' — правка; пусто — только удаление
    active: str = ''     # поле «показывать» (скрыть/вернуть без удаления)
    create: str = ''     # куда «Добавить ещё»

    def get_model(self):
        return apps.get_model(self.model)

    def get_form(self):
        if not self.form:
            return None
        mod, cls = self.form.rsplit('.', 1)
        return getattr(import_module(mod), cls)

    def title_of(self, obj) -> str:
        if self.title == 'route':
            return f'{obj.from_city} → {obj.to_city}'
        return str(getattr(obj, self.title, '') or obj)

    def url_of(self, obj) -> str:
        if not self.url:
            return ''
        return reverse(self.url, args=[obj.pk]) if ':' in self.url else self.url


PUBLICATIONS = [
    Pub('buy', 'Объявления', 'market.Listing', url='market:detail', form='apps.market.forms.ListingForm',
        active='is_active', create='/buy/add/'),
    Pub('jobs', 'Вакансии', 'jobs.Vacancy', url='jobs:detail', form='apps.jobs.forms.VacancyForm', create='/jobs/add/'),
    Pub('services', 'Услуги и фриланс', 'services.Service', title='name', url='/services/',
        form='apps.services.forms.ServiceForm', create='/services/add/'),
    Pub('transport', 'Перевозки', 'transport.Ride', title='route', url='/transport/',
        form='apps.transport.forms.RideForm', create='/transport/add/'),
    Pub('places', 'Места на карте', 'maps.HalalPlace', title='name', url='maps:detail',
        form='apps.maps.forms.HalalPlaceForm', create='/map/add/'),
    Pub('doctors', 'Врачи', 'health.Doctor', title='name', url='health:detail', form='apps.health.forms.DoctorForm',
        create='/health/add/'),
    Pub('stories', 'Истории переезда', 'migration.Story', owner='author', url='migration:detail',
        form='apps.migration.forms.StoryForm', create='/migration/add/'),
    Pub('books', 'Книги', 'library.Book', url='/library/', create='/library/add/'),
    Pub('topics', 'Вопросы на форуме', 'forum.Topic', owner='author', url='forum:detail',
        form='apps.forum.forms.TopicForm', create='/forum/ask/'),
]
BY_KEY = {p.key: p for p in PUBLICATIONS}


def pub_for_model(model):
    label = model._meta.label.lower()
    return next((p for p in PUBLICATIONS if p.model.lower() == label), None)
