"""«Мои публикации» (все разделы в одном месте) и жалобы."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.audit import log_action

from .models import Moderation, Report
from .publications import BY_KEY, PUBLICATIONS

STATUS_LABEL = {Moderation.PENDING: ('На проверке', 'pending'), Moderation.APPROVED: ('Опубликовано', 'ok'),
                Moderation.REJECTED: ('Отклонено', 'bad')}
AUTO_HIDE_AFTER = 3          # столько разных жалоб — и публикация скрыта до решения модератора
REPORTS_PER_DAY = 20         # защита от «жалобного» спама


@login_required
def my_publications(request):
    groups = []
    for pub in PUBLICATIONS:
        model = pub.get_model()
        items = []
        for obj in model.objects.filter(**{pub.owner: request.user}).order_by('-pk')[:100]:
            label, css = STATUS_LABEL.get(getattr(obj, 'status', ''), ('', ''))
            hidden = pub.active and not getattr(obj, pub.active)
            items.append({'obj': obj, 'title': pub.title_of(obj), 'url': pub.url_of(obj),
                          'status': 'Скрыто вами' if hidden else label, 'css': 'off' if hidden else css,
                          'public': not hidden and css == 'ok'})
        if items:
            groups.append({'pub': pub, 'items': items})
    return render(request, 'core/my_publications.html', {
        'groups': groups, 'create': [p for p in PUBLICATIONS if p.create]})


def _own(request, key, pk):
    pub = BY_KEY.get(key)
    if not pub:
        raise Http404
    obj = get_object_or_404(pub.get_model(), pk=pk, **{pub.owner: request.user})
    return pub, obj


@login_required
def my_edit(request, key, pk):
    """Правка своей публикации — после правки снова на модерацию (как на крупных площадках)."""
    pub, obj = _own(request, key, pk)
    form_cls = pub.get_form()
    if form_cls is None:
        messages.info(request, 'Эту публикацию можно только удалить и добавить заново.')
        return redirect('core:my')
    form = form_cls(request.POST or None, request.FILES or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        if hasattr(obj, 'status'):
            obj.status = Moderation.PENDING
        obj.save()
        form.save_m2m()
        log_action(request, f'Изменена публикация ({pub.label})', f'{key}#{obj.pk}')
        messages.success(request, 'Сохранено. После проверки модератором изменения появятся на сайте.')
        return redirect('core:my')
    return render(request, 'core/my_edit.html', {'form': form, 'pub': pub, 'obj': obj, 'title': pub.title_of(obj)})


@login_required
@require_POST
def my_delete(request, key, pk):
    pub, obj = _own(request, key, pk)
    title = pub.title_of(obj)
    obj.delete()
    log_action(request, f'Удалена публикация ({pub.label})', f'{key}#{pk}: {title}'[:200])
    messages.success(request, f'«{title}» удалено.')
    return redirect('core:my')


@login_required
@require_POST
def my_toggle(request, key, pk):
    pub, obj = _own(request, key, pk)
    if not pub.active:
        raise Http404
    setattr(obj, pub.active, not getattr(obj, pub.active))
    obj.save(update_fields=[pub.active])
    messages.success(request, 'Снова показывается.' if getattr(obj, pub.active) else 'Скрыто — никто не видит.')
    return redirect('core:my')


# ---------- жалобы ----------
REPORTABLE = {p.model.lower() for p in PUBLICATIONS} | {'nikah.nikahprofile', 'accounts.user', 'reviews.review'}


@login_required
@require_POST
def report(request):
    ct = get_object_or_404(ContentType, pk=request.POST.get('ct') or 0)
    if f'{ct.app_label}.{ct.model}' not in REPORTABLE:
        raise Http404
    model = ct.model_class()
    obj = get_object_or_404(model, pk=request.POST.get('id') or 0)
    reason = request.POST.get('reason', '')
    back = request.POST.get('next', '')
    back = back if url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}) else '/'
    if reason not in dict(Report.REASONS):
        messages.error(request, 'Выберите причину жалобы.')
        return redirect(back)
    key = f'reports:{request.user.pk}'
    if cache.get(key, 0) >= REPORTS_PER_DAY:
        messages.error(request, 'Слишком много жалоб за сегодня. Мы уже разбираемся.')
        return redirect(back)
    cache.set(key, cache.get(key, 0) + 1, 86400)
    owner = getattr(obj, 'owner', None) or getattr(obj, 'author', None) or getattr(obj, 'user', None)
    if obj == request.user or owner == request.user:
        messages.info(request, 'На себя жаловаться не нужно.')
        return redirect(back)
    _r, created = Report.objects.get_or_create(
        content_type=ct, object_id=obj.pk, reporter=request.user,
        defaults={'reason': reason, 'text': request.POST.get('text', '').strip()[:500]})
    if created:
        _after_report(ct, obj, reason)
    messages.success(request, 'Спасибо! Жалоба у модератора. Мы не сообщаем автору, кто пожаловался.')
    return redirect(back)


def _after_report(ct, obj, reason):
    count = Report.objects.filter(content_type=ct, object_id=obj.pk, status=Report.NEW).count()
    if count >= AUTO_HIDE_AFTER and getattr(obj, 'status', None) == Moderation.APPROVED:
        type(obj).objects.filter(pk=obj.pk).update(status=Moderation.PENDING)   # скрыть до решения
    try:
        from apps.tgbot.dispatch import moderation_chat
        chat = moderation_chat()
        if chat:
            from apps.accounts.telegram import api
            api('sendMessage', {'chat_id': chat, 'text': f'🚩 Жалоба ({dict(Report.REASONS)[reason]}): '
                                f'{ct.model} #{obj.pk} — {str(obj)[:120]}. Всего жалоб: {count}. '
                                f'Разобрать: админка → Жалобы.'})
    except ImportError:
        pass
