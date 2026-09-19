from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import module_required
from apps.core.models import Moderation
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
    return render(request, 'library/list.html', {
        'books': books[:60], 'categories': Book.CATEGORIES, 'cat': cat,
    })


@login_required
@module_required('library')
def book_download(request, pk):
    """Бесплатно — сразу; платная — купить один раз (списание с баланса)."""
    book = get_object_or_404(Book, pk=pk, status=Moderation.APPROVED)
    if book.price > 0 and not request.user.is_superuser:
        purchased = BookPurchase.objects.filter(book=book, user=request.user).exists()
        if not purchased:
            try:
                wallet.debit(request.user, book.price, Transaction.PURCHASE,
                             ref=f'library:book:{pk}', note=f'Покупка книги «{book.title}»')
            except InsufficientFunds:
                messages.error(request, 'Недостаточно средств — пополните кошелёк.')
                return redirect('wallet:index')
            BookPurchase.objects.create(book=book, user=request.user)
    return FileResponse(book.file.open('rb'), as_attachment=True,
                        filename=book.file.name.rsplit('/', 1)[-1])


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
                cover=request.FILES.get('cover'),
                file=upload, price=price_val, owner=request.user,
            )
            messages.success(request, 'Книга отправлена на модерацию.')
            return redirect('library:list')
    return render(request, 'library/add.html', {'allowed': ', '.join(sorted(ALLOWED_EXT))})
