"""Аудит безопасности: подбор пароля, восстановление, загрузки, платные действия."""
import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.models import Moderation
from apps.nikah.models import NikahProfile
from apps.wallet import services as wallet
from apps.wallet.models import Transaction

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def test_login_throttled_after_failures(client):
    User.objects.create_user('t', 't@x.com', 'right-pass-123')
    for _ in range(8):
        client.post('/accounts/login/', {'login': 't@x.com', 'password': 'wrong'})
    # даже верный пароль не пускает, пока не пройдёт окно
    resp = client.post('/accounts/login/', {'login': 't@x.com', 'password': 'right-pass-123'})
    assert resp.status_code == 429
    assert '_auth_user_id' not in client.session


def test_login_ok_below_limit(client):
    User.objects.create_user('t2', 't2@x.com', 'right-pass-123')
    for _ in range(3):
        client.post('/accounts/login/', {'login': 't2@x.com', 'password': 'wrong'})
    resp = client.post('/accounts/login/', {'login': 't2@x.com', 'password': 'right-pass-123'})
    assert resp.status_code == 302


def test_password_reset_sends_link_and_changes_password(client):
    User.objects.create_user('r', 'r@x.com', 'old-pass-123')
    resp = client.post('/accounts/password/reset/', {'email': 'r@x.com'})
    assert resp.status_code == 302
    assert len(mail.outbox) == 1
    link = next(line for line in mail.outbox[0].body.splitlines() if '/password/reset/' in line)
    path = link.split('testserver', 1)[1]
    resp = client.get(path, follow=True)            # токен → форма «новый пароль»
    assert resp.context['validlink']
    resp = client.post(resp.redirect_chain[-1][0], {'new_password1': 'N3w-strong-pass', 'new_password2': 'N3w-strong-pass'})
    assert resp.status_code == 302
    assert User.objects.get(email='r@x.com').check_password('N3w-strong-pass')


def test_password_reset_unknown_email_no_leak(client):
    resp = client.post('/accounts/password/reset/', {'email': 'nobody@x.com'})
    assert resp.status_code == 302 and len(mail.outbox) == 0   # тот же ответ, письма нет


def test_nikah_rejects_html_as_photo(client):
    from apps.nikah.tests.test_nikah import wizard_data
    user = User.objects.create_user('n', 'n@x.com', 'x')
    client.force_login(user)
    client.post('/nikah/create/', wizard_data(relocation='stay', photo_mode='exchange', photo=SimpleUploadedFile(
        'x.html', b'<script>alert(1)</script>', content_type='image/png')))
    assert not NikahProfile.objects.filter(user=user).exists()


def test_paid_actions_refuse_get(client):
    user = User.objects.create_user('g', 'g@x.com', 'x')
    wallet.credit(user, 100_000, Transaction.TOPUP)
    NikahProfile.objects.create(user=user, gender='M', age=30, about='о себе достаточно длинно',
                                status=Moderation.APPROVED)
    client.force_login(user)
    assert client.get('/nikah/me/boost/').status_code == 405
    assert wallet.balance_of(user) == 100_000


def test_nikah_accepts_real_photo(client):
    import io

    from PIL import Image

    from apps.nikah.tests.test_nikah import wizard_data
    buf = io.BytesIO()
    Image.new('RGB', (20, 20), 'green').save(buf, 'PNG')
    user = User.objects.create_user('n2', 'n2@x.com', 'x')
    client.force_login(user)
    client.post('/nikah/create/', wizard_data(relocation='stay', photo_mode='exchange', photo=SimpleUploadedFile(
        'me.png', buf.getvalue(), content_type='image/png')))
    assert NikahProfile.objects.get(user=user).has_photo
