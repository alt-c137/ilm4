"""Модерация прямо на сайте — для сотрудников, без захода в админку.

/moderation/ — одна очередь: анкеты никяха, публикации всех разделов (реестр
publications.PUBLICATIONS) и жалобы. Карточка показывает всё содержимое, вердикт
ИИ и автора; кнопки «Одобрить» / «Отклонить (с причиной)». Автор получает
уведомление (как и при решении из админки или Telegram).

Сотрудник видит на сайте и неодобренные публикации (visible()), а над ними —
панель модератора ({% staff_bar obj %} из templatetags/staff.py).
Права — как в админке: нужен is_staff и право «изменять» эту модель.
"""
from dataclasses import dataclass

from django.apps import apps
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.views.decorators.http import require_POST

from apps.accounts.audit import log_action

from .models import AIReview, Moderation, Report
from .publications import PUBLICATIONS


@dataclass(frozen=True)
class Source:
    key: str
    label: str
    model: str
    owner: str
    pub: object = None

    def get_model(self):
        return apps.get_model(self.model)

    def title_of(self, obj) -> str:
        if self.pub:
            return self.pub.title_of(obj)
        return f'{obj.display_name}, {obj.age}'

    def url_of(self, obj) -> str:
        if self.pub:
            return self.pub.url_of(obj)
        from django.urls import reverse
        return reverse('nikah:detail', args=[obj.pk])


SOURCES = [Source('nikah', _lazy('Анкеты никяха'), 'nikah.NikahProfile', 'user')] + [
    Source(p.key, p.label, p.model, p.owner, p) for p in PUBLICATIONS]
BY_KEY = {s.key: s for s in SOURCES}

# что не показываем в карточке: служебное, координаты, закрытое
SKIP = {'id', 'status', 'created_at', 'updated_at', 'is_active', 'boosted_until', 'premium_until', 'views',
        'lat', 'lon', 'platform_verified', 'photo', 'photo_private', 'faith_answers', 'agreed_at', 'verified',
        'verified_at', 'referred_by', 'ref_bonus_given', 'witness', 'witness_token', 'last_seen', 'cover', 'file'}


def is_moderator(user) -> bool:
    return user.is_authenticated and user.is_active and user.is_staff


def can_moderate(user, model) -> bool:
    meta = model._meta
    return is_moderator(user) and user.has_perm(f'{meta.app_label}.change_{meta.model_name}')


def visible(request, **public) -> dict:
    """Фильтр для детальной страницы: гостям — только одобренное, модератору — всё."""
    if is_moderator(request.user):
        return {}
    return {'status': Moderation.APPROVED, **public}


def pending_count(user) -> int:
    if not is_moderator(user):
        return 0
    n = Report.objects.filter(status=Report.NEW).values('content_type', 'object_id').distinct().count()
    for s in SOURCES:
        model = s.get_model()
        if can_moderate(user, model):
            n += model.objects.filter(status=Moderation.PENDING).count()
    return n


def _fields(obj, owner: str) -> list:
    rows = []
    for f in obj._meta.concrete_fields:
        if f.name in SKIP or f.name == owner or isinstance(f, (models.FileField, models.JSONField)):
            continue
        value = getattr(obj, f.name)
        if value in (None, '') or (isinstance(f, models.BooleanField) and not value):
            continue
        if f.choices:
            value = getattr(obj, f'get_{f.name}_display')()
        elif isinstance(f, models.BooleanField):
            value = _('да')
        rows.append((str(f.verbose_name).capitalize(), str(value)[:3000],
                     isinstance(f, models.TextField)))
    return rows


def _images(obj) -> list:
    out = []
    for f in obj._meta.concrete_fields:
        if isinstance(f, models.ImageField) and f.name not in ('photo_private',) and obj._meta.label != 'nikah.NikahProfile':
            v = getattr(obj, f.name)
            if v:
                try:
                    out.append(v.url)
                except ValueError:
                    pass
    return out


def _ai(obj):
    ct = ContentType.objects.get_for_model(obj)
    return AIReview.objects.filter(content_type=ct, object_id=obj.pk).first()


def card(src: Source, obj) -> dict:
    author = getattr(obj, src.owner, None)
    item = {'src': src, 'obj': obj, 'title': src.title_of(obj), 'author': author, 'fields': _fields(obj, src.owner),
            'images': _images(obj), 'ai': _ai(obj), 'url': src.url_of(obj),
            'created': getattr(obj, 'created_at', None), 'status': getattr(obj, 'status', '')}
    if src.key == 'nikah':
        from apps.nikah.choices import FAITH_QUESTIONS, FAITH_RED_FLAGS
        answers = obj.faith_answers or {}
        item['faith'] = [(q, {'yes': o[0], 'no': o[1]}.get(answers.get(k), '—'), answers.get(k) == FAITH_RED_FLAGS.get(k))
                         for k, q, o in FAITH_QUESTIONS]
        item['red'] = sum(1 for _q, _a, bad in item['faith'] if bad)
        item['has_photo'] = obj.has_photo
    if src.key == 'books' and obj.file:
        from django.urls import reverse
        item['file_url'] = reverse('library:download', args=[obj.pk])
    return item


def _reports(user) -> list:
    """Жалобы, сгруппированные по объекту: что за объект, сколько жалоб, причины."""
    groups = {}
    for r in Report.objects.filter(status=Report.NEW).select_related('content_type', 'reporter')[:300]:
        g = groups.setdefault((r.content_type_id, r.object_id), {'ct': r.content_type, 'id': r.object_id,
                                                                  'reports': [], 'obj': None})
        g['reports'].append(r)
    out = []
    for g in groups.values():
        model = g['ct'].model_class()
        if model is None or not can_moderate(user, model):
            continue
        g['obj'] = model.objects.filter(pk=g['id']).first()
        src = next((s for s in SOURCES if s.get_model() is model), None)
        g['src'] = src
        g['title'] = src.title_of(g['obj']) if (src and g['obj']) else str(g['obj'] or _('(удалено)'))
        g['url'] = src.url_of(g['obj']) if (src and g['obj']) else ''
        if model._meta.label == 'accounts.User' and g['obj']:
            from django.urls import reverse
            g['url'] = reverse('accounts:public', args=[g['obj'].pk])
        out.append(g)
    return out


def queue(request):
    if not is_moderator(request.user):
        raise Http404
    tab = request.GET.get('tab', '')
    sections, tabs = [], []
    for s in SOURCES:
        model = s.get_model()
        if not can_moderate(request.user, model):
            continue
        qs = model.objects.filter(status=Moderation.PENDING).order_by('created_at' if hasattr(model, 'created_at') else 'pk')
        n = qs.count()
        if n:
            tabs.append((s.key, s.label, n))
        if n and tab in ('', s.key):
            sections.append({'src': s, 'count': n, 'items': [card(s, o) for o in qs[:30]]})
    reports = _reports(request.user)
    if reports:
        tabs.append(('reports', _('Жалобы'), len(reports)))
    return render(request, 'core/moderation.html', {
        'sections': sections, 'tabs': tabs, 'tab': tab,
        'reports': reports if tab in ('', 'reports') else [], 'total': sum(t[2] for t in tabs),
        'reasons': [_('Контакты в тексте (телефон, ссылки, мессенджеры)'), _('Мало информации — дополните описание'),
                    _('Неприличное или харам-содержание'), _('Похоже на спам или обман'), _('Не тот раздел')]})


def _back(request, default='/moderation/'):
    url = request.POST.get('next', '')
    return url if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}) else default


def decide(src: Source, obj, approve: bool, reason: str = '') -> None:
    """Одобрить/отклонить — те же функции, что в админке и Telegram (с уведомлением автору)."""
    if src.key == 'nikah':
        from apps.nikah import bot
        bot.approve(obj) if approve else bot.reject(obj, reason)
        return
    obj.status = Moderation.APPROVED if approve else Moderation.REJECTED
    obj._reject_reason = reason               # сигнал допишет причину в уведомление автору
    obj.save(update_fields=['status'])


@require_POST
def act(request, key, pk):
    src = BY_KEY.get(key)
    if src is None:
        raise Http404
    model = src.get_model()
    if not can_moderate(request.user, model):
        raise PermissionDenied
    obj = get_object_or_404(model, pk=pk)
    do = request.POST.get('do')
    reason = request.POST.get('reason', '').strip()[:300]
    if do not in ('approve', 'reject'):
        raise Http404
    decide(src, obj, do == 'approve', reason)
    title = src.title_of(obj)
    log_action(request, f'{"Одобрено" if do == "approve" else "Отклонено"} на сайте ({src.label})',
               f'{key}#{pk}: {title}'[:200] + (f' — {reason}' if reason else ''))
    messages.success(request, (_('Одобрено: «{t}».') if do == 'approve' else _('Отклонено: «{t}». Автор получил уведомление.'))
                     .format(t=title[:60]))
    _drop_count(request)
    return redirect(_back(request))


def _drop_count(request):
    from django.core.cache import cache
    cache.delete(f'modpending:{request.user.pk}')


@require_POST
def report_act(request, ct, pk):
    """Жалоба: «оставить» (жалобы отклонены, объект снова виден) или «снять» (объект отклонён)."""
    ctype = get_object_or_404(ContentType, pk=ct)
    model = ctype.model_class()
    if model is None or not can_moderate(request.user, model):
        raise PermissionDenied
    do = request.POST.get('do')
    reports = Report.objects.filter(content_type=ctype, object_id=pk, status=Report.NEW)
    obj = model.objects.filter(pk=pk).first()
    src = next((s for s in SOURCES if s.get_model() is model), None)
    if do == 'dismiss':
        reports.update(status=Report.DISMISSED)
        if obj is not None and src and getattr(obj, 'status', None) == Moderation.PENDING:
            model.objects.filter(pk=pk).update(status=Moderation.APPROVED)   # был скрыт жалобами — вернуть
        messages.success(request, _('Жалобы отклонены, публикация остаётся.'))
    elif do == 'remove':
        reports.update(status=Report.RESOLVED)
        if obj is not None and src:
            decide(src, obj, False, request.POST.get('reason', '').strip()[:300])
        elif obj is not None and model._meta.label == 'accounts.User' and not obj.is_staff:
            obj.is_active = False
            obj.save(update_fields=['is_active'])
        messages.success(request, _('Меры приняты: снято с публикации.'))
    else:
        raise Http404
    log_action(request, f'Жалобы разобраны на сайте ({do})', f'{ctype.model}#{pk}')
    _drop_count(request)
    return redirect(_back(request))
