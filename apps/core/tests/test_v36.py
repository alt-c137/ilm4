"""v36: мои публикации, жалобы, блокировки, удаление аккаунта, уведомления авторам,
лимит публикаций, свидетель в никяхе, резюме, SEO."""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache

from apps.accounts.models import UserBlock
from apps.core.models import Moderation, Notification, Report
from apps.jobs.models import Vacancy

User = get_user_model()
pytestmark = pytest.mark.django_db
VAC = {'title': 'Повар', 'category': 'other', 'company': 'Халяль кафе', 'city': 'Ташкент',
       'description': 'Кухня, график 5/2', 'contact': '@hr'}


@pytest.fixture(autouse=True)
def _cache():
    cache.clear()
    yield
    cache.clear()


def _user(name):
    return User.objects.create_user(name, f'{name}@x.com', 'x')


def test_my_publications_edit_delete_only_own(client):
    me, other = _user('me'), _user('other')
    mine = Vacancy.objects.create(owner=me, status=Moderation.APPROVED, **VAC)
    theirs = Vacancy.objects.create(owner=other, status=Moderation.APPROVED, **{**VAC, 'title': 'Чужая'})
    client.force_login(me)
    html = client.get('/my/').content.decode()
    assert 'Повар' in html and 'Чужая' not in html and 'Опубликовано' in html
    client.post(f'/my/jobs/{mine.pk}/edit/', {**VAC, 'kind': 'vacancy', 'title': 'Шеф-повар'})
    mine.refresh_from_db()
    assert mine.title == 'Шеф-повар' and mine.status == Moderation.PENDING   # правка — снова на проверку
    assert client.post(f'/my/jobs/{theirs.pk}/delete/').status_code == 404
    client.post(f'/my/jobs/{mine.pk}/delete/')
    assert not Vacancy.objects.filter(pk=mine.pk).exists() and Vacancy.objects.filter(pk=theirs.pk).exists()


def test_my_toggle_hides_listing(client):
    from apps.market.models import Category, Listing
    me = _user('me')
    cat = Category.objects.create(name='Разное', slug='misc')
    item = Listing.objects.create(owner=me, title='Коврик', description='Новый', price=100, category=cat,
                                  city='Ташкент', status=Moderation.APPROVED)
    client.force_login(me)
    client.post(f'/my/buy/{item.pk}/toggle/')
    item.refresh_from_db()
    assert not item.is_active
    assert client.get(f'/buy/{item.pk}/').status_code == 404


def test_author_notified_on_admin_approve():
    from apps.core.signals import set_status
    me = _user('me')
    v = Vacancy.objects.create(owner=me, **VAC)
    set_status(Vacancy.objects.filter(pk=v.pk), Moderation.APPROVED)
    assert Notification.objects.filter(user=me, text__contains='одобрено').exists()


def test_reports_autohide_after_three(client):
    owner = _user('owner')
    v = Vacancy.objects.create(owner=owner, status=Moderation.APPROVED, **VAC)
    ct = ContentType.objects.get_for_model(Vacancy).pk
    for i in range(3):
        client.force_login(_user(f'r{i}'))
        client.post('/report/', {'ct': ct, 'id': v.pk, 'reason': 'fraud', 'next': '/jobs/'})
        client.post('/report/', {'ct': ct, 'id': v.pk, 'reason': 'fraud', 'next': '/jobs/'})   # повтор не считается
    assert Report.objects.count() == 3
    v.refresh_from_db()
    assert v.status == Moderation.PENDING          # скрыто до решения модератора


def test_report_whitelist_and_not_self(client):
    owner = _user('owner')
    client.force_login(owner)
    v = Vacancy.objects.create(owner=owner, status=Moderation.APPROVED, **VAC)
    client.post('/report/', {'ct': ContentType.objects.get_for_model(Vacancy).pk, 'id': v.pk, 'reason': 'spam'})
    assert not Report.objects.exists()
    ct_session = ContentType.objects.get(app_label='sessions', model='session').pk
    assert client.post('/report/', {'ct': ct_session, 'id': 1, 'reason': 'spam'}).status_code == 404


def test_block_stops_chat(client):
    a, b = _user('a'), _user('b')
    client.force_login(a)
    client.post(f'/accounts/u/{b.pk}/block/')
    assert UserBlock.between(a, b)
    client.force_login(b)
    resp = client.get(f'/chat/start/?user={a.pk}')
    assert resp.status_code == 302 and resp.url == '/chat/'
    client.force_login(a)
    client.post(f'/accounts/u/{b.pk}/block/')          # повторно — разблокировать
    assert not UserBlock.between(a, b)


def test_block_hides_in_nikah(client):
    from apps.nikah.tests.test_nikah import make_profile
    b = make_profile('b@x.com', 'M')
    s = make_profile('s@x.com', 'F', name='Скрытая')
    UserBlock.objects.create(blocker=s.user, blocked=b.user)
    client.force_login(b.user)
    assert 'Скрытая' not in client.get('/nikah/').content.decode()
    assert client.get(f'/nikah/{s.pk}/').status_code == 404


def test_delete_account_wipes_personal_data(client):
    from apps.nikah.tests.test_nikah import make_profile
    p = make_profile('del@x.com', 'M')
    user = p.user
    Vacancy.objects.create(owner=user, status=Moderation.APPROVED, **VAC)
    client.force_login(user)
    client.post('/accounts/delete/', {'confirm': 'нет'})
    assert User.objects.get(pk=user.pk).is_active
    client.post('/accounts/delete/', {'confirm': 'удалить'})
    user.refresh_from_db()
    assert not user.is_active and 'del@' not in user.email and not hasattr(user, 'nikah_profile')
    assert Vacancy.objects.get(owner=user).status == Moderation.REJECTED
    assert '_auth_user_id' not in client.session


def test_publish_daily_limit(client):
    from apps.core import decorators
    me = _user('me')
    client.force_login(me)
    for _ in range(decorators.PUBLISH_PER_DAY):
        client.post('/jobs/add/', {**VAC, 'kind': 'vacancy', 'pledge': '1'})
    n = Vacancy.objects.count()
    client.post('/jobs/add/', {**VAC, 'kind': 'vacancy', 'pledge': '1'})
    assert Vacancy.objects.count() == n == decorators.PUBLISH_PER_DAY


def test_resume_kind(client):
    me = _user('me')
    client.force_login(me)
    client.post('/jobs/add/', {**VAC, 'kind': 'resume', 'company': '', 'title': 'Ищу работу водителем',
                               'pledge': '1'})
    r = Vacancy.objects.get()
    assert r.is_resume
    Vacancy.objects.filter(pk=r.pk).update(status=Moderation.APPROVED)
    assert 'Ищу работу водителем' in client.get('/jobs/?kind=resume').content.decode()
    assert 'Ищу работу водителем' not in client.get('/jobs/').content.decode()
    client.post('/jobs/add/', {**VAC, 'kind': 'vacancy', 'company': '', 'pledge': '1'})
    assert Vacancy.objects.count() == 1        # вакансии без компании нельзя


def test_nikah_witness_sees_chat(client):
    from apps.nikah import services
    from apps.nikah.tests.test_nikah import make_profile
    b = make_profile('b@x.com', 'M')
    s = make_profile('s@x.com', 'F')
    services.send_interest(b, s)
    m = services.send_interest(s, b)
    father = _user('father')
    client.force_login(s.user)
    client.post('/nikah/witness/')
    s.refresh_from_db()
    client.force_login(father)
    client.post(f'/nikah/witness/{s.witness_token}/')
    m.refresh_from_db()
    assert m.thread.participants.filter(pk=father.pk).exists()
    assert m.thread.other_participant(s.user) == b.user        # собеседник — брат, а не свидетель
    assert client.get(f'/chat/{m.thread_id}/').status_code == 200
    s.refresh_from_db()
    assert s.witness_token == ''                                 # ссылка одноразовая


def test_seo_endpoints(client):
    assert 'Disallow: /admin/' in client.get('/robots.txt').content.decode()
    assert client.get('/sitemap.xml').status_code == 200
    assert client.get('/sw.js')['Service-Worker-Allowed'] == '/'
