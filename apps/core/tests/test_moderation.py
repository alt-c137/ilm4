"""Модерация на сайте (без админки) и подтверждение номера через Telegram."""
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts import phone_verify
from apps.core.models import Moderation, ModuleConfig, Notification, Report
from apps.jobs.models import Vacancy
from apps.nikah.tests.test_nikah import make_profile

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def mod(client):
    """Сотрудник с пройденной 2FA (иначе Staff2FARequired уводит на подтверждение)."""
    u = User.objects.create_user('mod', 'mod@x.com', 'x', is_staff=True, is_superuser=True)
    dev = TOTPDevice.objects.create(user=u, name='t', confirmed=True)
    client.force_login(u)
    s = client.session
    s['otp_device_id'] = dev.persistent_id
    s.save()
    return u


def _on(*keys):
    for k in keys:
        ModuleConfig.objects.update_or_create(key=k, defaults={'name': k, 'status': 'on'})


def test_queue_hidden_from_users(client):
    client.force_login(User.objects.create_user('u', 'u@x.com', 'x'))
    assert client.get('/moderation/').status_code == 404


def test_approve_nikah_profile_on_site(client, mod):
    _on('nikah')
    p = make_profile('b@x.com', 'M', status=Moderation.PENDING)
    html = client.get('/moderation/').content.decode()
    assert 'Имя, 27' in html and f'/moderation/nikah/{p.pk}/' in html
    # модератор видит анкету на проверке — даже того же пола (раньше тут было 404)
    assert client.get(f'/nikah/{p.pk}/').status_code == 200
    r = client.post(f'/moderation/nikah/{p.pk}/', {'do': 'approve', 'next': '/moderation/'})
    assert r.status_code == 302
    p.refresh_from_db()
    assert p.status == Moderation.APPROVED
    assert Notification.objects.filter(user=p.user).exists()


def test_reject_publication_with_reason(client, mod):
    _on('jobs')
    owner = User.objects.create_user('o', 'o@x.com', 'x')
    v = Vacancy.objects.create(title='Повар', description='Нужен повар', contact='@x', owner=owner,
                               status=Moderation.PENDING)
    assert client.get(f'/jobs/{v.pk}/').status_code == 200          # модератор видит неодобренное
    assert 'staffbar' in client.get(f'/jobs/{v.pk}/').content.decode()
    client.post(f'/moderation/jobs/{v.pk}/', {'do': 'reject', 'reason': 'уберите номер'})
    v.refresh_from_db()
    assert v.status == Moderation.REJECTED
    assert 'уберите номер' in Notification.objects.get(user=owner).text


def test_guest_does_not_see_pending(client):
    _on('jobs')
    owner = User.objects.create_user('o', 'o@x.com', 'x')
    v = Vacancy.objects.create(title='Повар', description='-', contact='-', owner=owner, status=Moderation.PENDING)
    assert client.get(f'/jobs/{v.pk}/').status_code == 404


def test_reports_dismiss_returns_item(client, mod):
    from django.contrib.contenttypes.models import ContentType
    _on('jobs')
    owner = User.objects.create_user('o', 'o@x.com', 'x')
    v = Vacancy.objects.create(title='Повар', description='-', contact='-', owner=owner, status=Moderation.PENDING)
    ct = ContentType.objects.get_for_model(Vacancy)
    Report.objects.create(content_type=ct, object_id=v.pk, reporter=owner, reason='spam')
    assert 'Спам' in client.get('/moderation/?tab=reports').content.decode()
    client.post(f'/moderation/report/{ct.pk}/{v.pk}/', {'do': 'dismiss'})
    v.refresh_from_db()
    assert v.status == Moderation.APPROVED
    assert not Report.objects.filter(status=Report.NEW).exists()


# ---------- подтверждение номера ----------

@pytest.fixture
def bot(settings, monkeypatch):
    settings.TELEGRAM_BOT_TOKEN = 'x'
    settings.TELEGRAM_BOT_USERNAME = 'ilm4bot'
    sent = []
    monkeypatch.setattr('apps.tgbot.dispatch.reply', lambda chat, text, markup=None: sent.append((text, markup)))
    cache.clear()
    return sent


def _contact(tg_id, phone, owner=None):
    return {'chat': {'id': tg_id, 'type': 'private'}, 'from': {'id': tg_id, 'first_name': 'A'},
            'contact': {'phone_number': phone, 'user_id': tg_id if owner is None else owner}}


def test_publish_requires_phone_then_works(client, bot):
    _on('jobs')
    u = User.objects.create_user('p', 'p@x.com', 'x')
    client.force_login(u)
    r = client.get('/jobs/add/')
    assert r.status_code == 302 and r.url.startswith('/accounts/phone/')
    page = client.get(r.url).content.decode()
    assert 't.me/ilm4bot?start=phone_' in page
    nonce = page.split('start=phone_')[1].split('"')[0]

    from apps.tgbot.dispatch import start
    start({'chat': {'id': 77}, 'from': {'id': 77}}, f'phone_{nonce}')
    assert bot[-1][1]['keyboard'][0][0]['request_contact'] is True
    phone_verify.bot_contact(_contact(77, '+998 90 123 45 67', owner=555))     # чужой контакт — нельзя
    u.refresh_from_db()
    assert not u.phone_verified
    phone_verify.bot_contact(_contact(77, '+998 90 123 45 67'))
    u.refresh_from_db()
    assert u.phone_verified and u.phone == '+998901234567' and u.telegram_id == 77
    assert client.get(f'/accounts/phone/status/?nonce={nonce}').json()['verified'] is True
    assert client.get('/jobs/add/').status_code == 200


def test_one_phone_one_account(client, bot):
    a = User.objects.create_user('a', 'a@x.com', 'x')
    b = User.objects.create_user('b', 'b@x.com', 'x')
    phone_verify.confirm(a, '+998901234567')
    with pytest.raises(ValueError):
        phone_verify.confirm(b, '8 90 123-45-67')


def test_nikah_requires_phone_and_admin_can_turn_off(client, bot):
    from apps.core.models import SiteSettings
    _on('nikah')
    u = User.objects.create_user('n', 'n@x.com', 'x')
    client.force_login(u)
    assert client.get('/nikah/create/').url.startswith('/accounts/phone/?')
    SiteSettings.objects.update(phone_for_nikah=False)
    assert client.get('/nikah/create/').status_code == 200


def test_api_phone_flow(client, bot):
    from apps.api.models import ApiToken
    _on('jobs', 'nikah')
    u = User.objects.create_user('api', 'api@x.com', 'x')
    h = {'HTTP_AUTHORIZATION': f'Bearer {ApiToken.issue(u, "t")}'}
    r = client.get('/api/v1/pubs/jobs/form/', **h)
    assert r.status_code == 403 and r.json()['code'] == 'phone'
    assert client.get('/api/v1/nikah/state/', **h).json()['code'] == 'phone'
    assert client.get('/api/v1/me/', **h).json()['needs_phone'] == {'publish': True, 'nikah': True}
    link = client.post('/api/v1/auth/phone/', **h).json()
    assert link['url'].startswith('https://t.me/ilm4bot?start=phone_')
    from apps.tgbot.dispatch import start
    start({'chat': {'id': 9}, 'from': {'id': 9}}, f'phone_{link["nonce"]}')
    phone_verify.bot_contact(_contact(9, '+998911112233'))
    assert client.get(f'/api/v1/auth/phone/status/?nonce={link["nonce"]}', **h).json()['verified'] is True
    assert client.get('/api/v1/pubs/jobs/form/', **h).status_code == 200


def test_staff_and_no_bot_skip_phone(client, settings):
    settings.TELEGRAM_BOT_TOKEN = ''
    _on('jobs')
    u = User.objects.create_user('q', 'q@x.com', 'x')
    client.force_login(u)
    assert client.get('/jobs/add/').status_code == 200          # бот не подключён — не мешаем
