"""Фаза 0 — каркас: главная, страницы, темы, статусы разделов (§3)."""
import pytest
from django.http import Http404
from django.test import RequestFactory

from apps.core.decorators import module_required
from apps.core.models import ModuleConfig, Theme

pytestmark = pytest.mark.django_db


def test_home(client):
    response = client.get('/')
    assert response.status_code == 200
    html = response.content.decode()
    assert 'Разделы платформы' in html
    assert 'скоро' in html          # все модули на старте — «скоро»
    assert 'Время намаза' in html   # модуль из сидинга присутствует на витрине


def test_static_pages(client):
    for url in ['/rules/', '/privacy/', '/support/', '/soon/']:
        assert client.get(url).status_code == 200, url


def test_theme_cookie_sets_current(client):
    theme = Theme.objects.order_by('order').first()
    response = client.get('/', HTTP_COOKIE=f'ilm4_theme={theme.id}')
    assert response.context['current_theme'].id == theme.id
    # и в inline-стиле главной отдаются цвета темы
    assert theme.accent in response.content.decode()


def test_theme_fallback_to_default(client):
    default = Theme.objects.order_by('order').first()
    response = client.get('/')
    assert response.context['current_theme'].id == default.id


def _view_for(key):
    @module_required(key)
    def view(request):
        return 'CALLED'
    return view


def test_module_required_all_statuses():
    factory = RequestFactory()
    request = factory.get('/')
    module = ModuleConfig.objects.create(key='tst', name='Тест')

    module.status = ModuleConfig.SOON
    module.save()
    response = _view_for('tst')(request)
    assert response.status_code == 200
    assert 'Тест' in response.content.decode()

    module.status = ModuleConfig.ON
    module.save()
    assert _view_for('tst')(request) == 'CALLED'

    module.status = ModuleConfig.OFF
    module.save()
    with pytest.raises(Http404):
        _view_for('tst')(request)

    with pytest.raises(Http404):  # записи нет — раздел выключен
        _view_for('no-such-module')(request)


def test_seeded_themes():
    assert Theme.objects.count() == 6


def test_seeded_modules_all_soon():
    assert ModuleConfig.objects.exclude(status=ModuleConfig.SOON).count() == 0
    assert ModuleConfig.objects.count() >= 18
