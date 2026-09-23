from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import content_disposition_header

from apps.core.decorators import module_required
from apps.core.models import Moderation
from apps.core.uploads import clean_image
from apps.wallet import services as wallet
from apps.wallet.models import Transaction
from apps.wallet.services import InsufficientFunds

from .models import Book, BookPurchase

ALLOWED_EXT = {'.pdf', '.epub', '.fb2', '.mobi', '.djvu'}
MAX_FILE_MB = 50


@module_required('library')
def book_list(request):
    books = Book.objects.filter(status=Moderation.APPROVED)
    cat = request.GET.get('cat', '').strip()
    if cat in dict(Book.CATEGORIES):
        books = books.filter(category=cat)
    owned = set()
    if request.user.is_authenticated:
        owned = set(request.user.book_purchases.values_list('book_id', flat=True))
        owned |= set(request.user.books.values_list('pk', flat=True))
    return render(request, 'library/list.html', {
        'books': books[:60], 'categories': Book.CATEGORIES, 'cat': cat, 'owned': owned,
    })


def _serve_book(book):
    """Файл книги — только через эту проверку: прямой /media/books/files/ закрыт в nginx."""
    name = book.file.name.rsplit('/', 1)[-1]
    if getattr(settings, 'CHAT_XACCEL', False):
        resp = HttpResponse(content_type='application/octet-stream')
        resp['X-Accel-Redirect'] = '/protected-media/' + book.file.name
        resp['Content-Disposition'] = content_disposition_header(True, name)
        return resp
    return FileResponse(book.file.open('rb'), as_attachment=True, filename=name)


@login_required
@module_required('library')
def book_download(request, pk):
    """Бесплатно — сразу; платная — покупка один раз (только POST, со списанием с баланса),
    потом скачивание без повторной оплаты."""
    book = get_object_or_404(Book, pk=pk, status=Moderation.APPROVED)
    free = book.price <= 0 or request.user.is_superuser or book.owner_id == request.user.pk
    if free or BookPurchase.objects.filter(book=book, user=request.user).exists():
        return _serve_book(book)
    if request.method != 'POST':
        messages.info(request, f'«{book.title}» — платная книга: нажмите «Купить».')
        return redirect('library:list')
    try:
        with transaction.atomic():
            _purchase, created = BookPurchase.objects.get_or_create(book=book, user=request.user)
            if created:
                wallet.debit(request.user, book.price, Transaction.PURCHASE,
                             ref=f'library:book:{pk}', note=f'Покупка книги «{book.title}»')
    except InsufficientFunds:
        messages.error(request, 'Недостаточно средств — пополните кошелёк.')
        return redirect('wallet:index')
    return _serve_book(book)


@login_required
@module_required('library')
def book_add(request):
    """Добавление книги: название + файл (+цена). Проверка типа и размера."""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()[:200]
        price = request.POST.get('price', '0').strip() or '0'
        upload = request.FILES.get('file')
        errors = []
        if not title:
            errors.append('Укажите название.')
        if not upload:
            errors.append('Загрузите файл книги.')
        else:
            from pathlib import PurePosixPath

            ext = ''.join(PurePosixPath(upload.name).suffix.lower())
            if ext not in ALLOWED_EXT:
                errors.append(f'Формат {ext or "неизвестный"} не поддерживается '
                              f'(можно: {", ".join(sorted(ALLOWED_EXT))}).')
            elif upload.size > MAX_FILE_MB * 1024 * 1024:
                errors.append(f'Файл больше {MAX_FILE_MB} МБ.')
        try:
            cover = clean_image(request.FILES.get('cover'))
        except ValidationError as exc:
            cover = None
            errors.append('Обложка: ' + (exc.messages[0] if exc.messages else 'нужна картинка JPG или PNG.'))
        try:
            price_val = max(0, int(price))
        except ValueError:
            errors.append('Цена — целое число.')
            price_val = 0
        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            cat = request.POST.get('category', 'other')
            if cat not in dict(Book.CATEGORIES):
                cat = 'other'
            Book.objects.create(
                title=title,
                category=cat,
                author=request.POST.get('author', '').strip()[:160],
                description=request.POST.get('description', ''),
                cover=cover,
                file=upload, price=price_val, owner=request.user,
            )
            messages.success(request, 'Книга отправлена на модерацию.')
            return redirect('library:list')
    return render(request, 'library/add.html', {'allowed': ', '.join(sorted(ALLOWED_EXT))})
