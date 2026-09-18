"""Фаза 6 — новости: список, деталь, блок на главной."""
import pytest

from apps.news.models import NewsPost

pytestmark = pytest.mark.django_db


def test_news_list_and_detail(client):
    post = NewsPost.objects.create(title='Приём в Университет Медины',
                                   slug='madina-2027', body='Открыт приём документов.')
    html = client.get('/news/').content.decode()
    assert 'Приём в Университет Медины' in html
    detail = client.get(f'/news/{post.slug}/')
    assert detail.status_code == 200
    assert 'Открыт приём документов' in detail.content.decode()
