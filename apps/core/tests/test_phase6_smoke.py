"""Фаза 6 — smoke: все контент-разделы включены и отвечают."""
import pytest

from apps.core.models import ModuleConfig

pytestmark = pytest.mark.django_db


def test_all_sections_enabled():
    on = set(ModuleConfig.objects.filter(status='on').values_list('key', flat=True))
    assert {'prayer', 'map', 'health', 'buy', 'news', 'forum',
            'jobs', 'migration', 'services', 'library'} <= on


def test_sections_respond(client):
    for url in ['/news/', '/forum/', '/jobs/', '/migration/', '/services/', '/library/']:
        response = client.get(url)
        assert response.status_code == 200, url
