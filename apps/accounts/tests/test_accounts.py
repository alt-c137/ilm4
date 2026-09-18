"""Фаза 1 — accounts: регистрация, вход по email, роли, 2FA, аудит."""
import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import AuditLog, RegistrationField
from apps.accounts.roles import admin_required

User = get_user_model()
pytestmark = pytest.mark.django_db


# ---------- регистрация и вход ----------

def test_register_creates_and_logs_in(client):
    response = client.post('/accounts/register/', {
        'email': 'test@example.com',
        'username': '',
        'password1': 'Str0ng-Pass!2026',
        'password2': 'Str0ng-Pass!2026',
        'nickname': 'Тестёр',
        'city': 'Ташкент',
    })
    assert response.status_code == 302
    user = User.objects.get(email='test@example.com')
    assert user.nickname == 'Тестёр'
    assert '_auth_user_id' in client.session  # автологин


def test_register_duplicate_email_blocked(client):
    User.objects.create_user('a', 'dup@example.com', 'x')
    response = client.post('/accounts/register/', {
        'email': 'dup@example.com',
        'password1': 'Str0ng-Pass!2026',
        'password2': 'Str0ng-Pass!2026',
    })
    assert 'уже зарегистрирован' in response.content.decode()


def test_login_by_email(client):
    User.objects.create_user('alice', 'alice@example.com', 'S3cret-Pass!')
    ok = client.post('/accounts/login/', {'login': 'alice@example.com', 'password': 'S3cret-Pass!'})
    assert ok.status_code == 302
    assert '_auth_user_id' in client.session


def test_login_by_username(client):
    User.objects.create_user('alice', 'alice@example.com', 'S3cret-Pass!')
    ok = client.post('/accounts/login/', {'login': 'alice', 'password': 'S3cret-Pass!'})
    assert ok.status_code == 302


def test_login_wrong_password(client):
    User.objects.create_user('alice', 'alice@example.com', 'S3cret-Pass!')
    bad = client.post('/accounts/login/', {'login': 'alice@example.com', 'password': 'nope'})
    assert bad.status_code == 200
    assert 'Неверный' in bad.content.decode()


# ---------- гибкие поля регистрации ----------

def test_registration_fields_from_admin(client):
    RegistrationField.objects.filter(key='city').update(enabled=False)
    form_response = client.get('/accounts/register/')
    html = form_response.content.decode()
    assert 'Город' not in html
    assert 'Ник' in html  # включён по сидингу


# ---------- роли ----------

def test_role_properties():
    user = User.objects.create_user('u1', 'u1@x.com', 'x', role='admin')
    superu = User.objects.create_user('su', 'su@x.com', 'x', is_superuser=True)
    assert user.is_admin_role and not user.is_super_admin
    assert superu.is_super_admin and superu.is_admin_role


def test_admin_required_denies_plain_user(rf):
    @admin_required
    def view(request):
        return 'OK'
    plain = User.objects.create_user('p', 'p@x.com', 'x')
    request = rf.get('/')
    request.user = plain
    from django.core.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        view(request)


# ---------- 2FA обязательна для staff ----------

def test_staff_without_2fa_redirected(client, settings):
    staff = User.objects.create_user('staff', 'staff@x.com', 'x', is_staff=True)
    client.force_login(staff)
    response = client.get('/admin/')
    assert response.status_code == 302
    assert '/accounts/2fa' in response.url


def test_normal_user_not_redirected(client):
    user = User.objects.create_user('plain', 'plain@x.com', 'x')
    client.force_login(user)
    assert client.get('/').status_code == 200


# ---------- аудит ----------

def test_staff_login_audited(client):
    User.objects.create_user('staff', 'staff@x.com', 'x', is_staff=True)
    client.post('/accounts/login/', {'login': 'staff@x.com', 'password': 'x'})
    assert AuditLog.objects.filter(action='Вход администратора').exists()


# ---------- профиль ----------

def test_profile_update(client):
    user = User.objects.create_user('bob', 'bob@x.com', 'x')
    client.force_login(user)
    client.post('/accounts/profile/', {'nickname': 'Бобр', 'first_name': '', 'city': 'Бухара', 'theme': ''})
    user.refresh_from_db()
    assert user.nickname == 'Бобр' and user.city == 'Бухара'
