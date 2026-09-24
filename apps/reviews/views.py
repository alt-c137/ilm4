"""Отправка отзыва и ответ владельца. Только POST, только разрешённые типы."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.audit import log_action

from .models import REVIEWABLE, Review
from .services import can_review, is_rated, owner_of


def _target(ct_id, obj_id):
    ct = get_object_or_404(ContentType, pk=ct_id)
    if f'{ct.app_label}.{ct.model}' not in REVIEWABLE:
        raise Http404
    try:
        return ct, ct.get_object_for_this_type(pk=obj_id)
    except ct.model_class().DoesNotExist:
        raise Http404 from None


def _back(request):
    nxt = request.POST.get('next', '')
    if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt + '#reviews')
    return redirect('core:home')


@login_required
@require_POST
def submit(request, ct_id, obj_id):
    ct, obj = _target(ct_id, obj_id)
    if not can_review(request.user, obj):
        messages.error(request, _('Оценивать свою страницу нельзя.'))
        return _back(request)
    text = request.POST.get('text', '').strip()[:2000]
    if is_rated(obj):
        try:
            rating = int(request.POST.get('rating', 0))
        except ValueError:
            rating = 0
        if not 1 <= rating <= 5:
            messages.error(request, _('Поставьте оценку от 1 до 5 звёзд.'))
            return _back(request)
    else:
        rating = None
        if not text:
            messages.error(request, _('Напишите сообщение.'))
            return _back(request)
    _review, created = Review.objects.update_or_create(
        content_type=ct, object_id=obj.pk, author=request.user,
        defaults={'rating': rating, 'text': text})
    log_action(request, 'Отзыв ' + ('оставлен' if created else 'изменён'), f'{ct.model}#{obj.pk}: {rating or "—"}★')
    messages.success(request, _('Спасибо! Отзыв опубликован.') if created else _('Отзыв обновлён.'))
    return _back(request)


@login_required
@require_POST
def reply(request, pk):
    review = get_object_or_404(Review, pk=pk)
    owner = owner_of(review.target)
    if owner is None or owner.pk != request.user.pk:
        raise Http404
    review.reply = request.POST.get('reply', '').strip()[:2000]
    review.replied_at = timezone.now() if review.reply else None
    review.save(update_fields=['reply', 'replied_at'])
    messages.success(request, _('Ответ сохранён.'))
    return _back(request)
