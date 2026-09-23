"""Фаза 6 — библиотека: бесплатная книга, платная покупка, валидация файла."""
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.models import Moderation
from apps.library.models import Book
from apps.wallet import services as wallet
from apps.wallet.models import Transaction

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_book(title='Таухид для начинающих', price=0, filename='book.pdf', content=b'%PDF-1.4'):
    return Book.objects.create(
        title=title, price=price, status=Moderation.APPROVED,
        file=SimpleUploadedFile(filename, content),
    )


def test_free_book_downloads(client):
    user = User.objects.create_user('u', 'u@x.com', 'x')
    book = make_book()
    client.force_login(user)
    response = client.get(f'/library/{book.pk}/download/')
    assert response.status_code == 200
    assert wallet.balance_of(user) == 0  # бесплатная — без списаний


def test_paid_book_purchase_once(client):
    user = User.objects.create_user('u2', 'u2@x.com', 'x')
    wallet.credit(user, 100_000, Transaction.TOPUP)
    book = make_book(title='Комментарий к аль-Фатихе', price=60_000)
    client.force_login(user)
    # GET платную не покупает: иначе чужой сайт спишет деньги ссылкой-картинкой
    assert client.get(f'/library/{book.pk}/download/').status_code == 302
    assert wallet.balance_of(user) == 100_000
    assert client.post(f'/library/{book.pk}/download/').status_code == 200
    assert wallet.balance_of(user) == 40_000  # куплено

    client.get(f'/library/{book.pk}/download/')  # повторное скачивание
    assert wallet.balance_of(user) == 40_000  # без повторного списания


def test_paid_book_insufficient(client):
    user = User.objects.create_user('u3', 'u3@x.com', 'x')
    book = make_book(title='Дорогая книга', price=999_999)
    client.force_login(user)
    response = client.post(f'/library/{book.pk}/download/')
    assert response.status_code == 302 and '/wallet/' in response.url
    assert not book.purchases.exists()   # покупка откатилась вместе со списанием


def test_add_book_rejects_exe(client):
    user = User.objects.create_user('u4', 'u4@x.com', 'x')
    client.force_login(user)
    client.post('/library/add/', {
        'title': 'Вредная книга',
        'file': SimpleUploadedFile('virus.exe', b'MZ...'),
        'price': '0',
    })
    assert not Book.objects.filter(title='Вредная книга').exists()
