"""API: подача и правка своих публикаций из приложения, «Мои публикации».

Формы — те же, что на сайте (apps/core/publications.py → Pub.form), поэтому проверки,
модерация и правила одинаковы. Приложение получает описание полей (/form/) и само
строит экран; новый раздел с формой появляется в приложении без его обновления.
"""
from django import forms
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from apps.accounts.audit import log_action
from apps.core.decorators import PUBLISH_PER_DAY
from apps.core.models import Moderation, SiteSettings
from apps.core.publications import BY_KEY, PUBLICATIONS

from .base import MODULE_OF, ApiError, api, file_url, module_on

PLEDGE = [
    _lazy('Я публикую правдивые сведения — без обмана, скрытых недостатков и завышенных обещаний.'),
    _lazy('Я выполню то, о чём договорюсь: цену, сроки, качество и условия.'),
    _lazy('Я отвечаю за свою публикацию и её исполнение — перед людьми и перед Аллахом. ilm4 — лишь площадка и не участвует в договорённостях.'),
]
STATUS = {Moderation.PENDING: _lazy('На проверке'), Moderation.APPROVED: _lazy('Опубликовано'),
          Moderation.REJECTED: _lazy('Отклонено')}


def _pub(key):
    pub = BY_KEY.get(key)
    if pub is None or not pub.form or not module_on(MODULE_OF.get(key, key)):
        raise Http404
    return pub


def _kind(field) -> str:
    w = field.widget
    if isinstance(field, forms.ImageField):
        return 'image'
    if isinstance(field, forms.FileField):
        return 'file'
    if isinstance(field, forms.BooleanField):
        return 'bool'
    if isinstance(field, forms.ChoiceField):   # и ModelChoiceField (подкласс)
        return 'choice'
    if isinstance(field, forms.DateField):
        return 'date'
    if isinstance(field, (forms.IntegerField, forms.DecimalField, forms.FloatField)):
        return 'number'
    if isinstance(w, forms.Textarea):
        return 'text'
    if isinstance(field, forms.URLField):
        return 'url'
    return 'line'


def _value(v):
    if v is None:
        return ''
    if hasattr(v, 'isoformat'):
        return v.isoformat()
    if hasattr(v, 'pk'):
        return v.pk
    if isinstance(v, bool):
        return v
    return str(v) if not isinstance(v, (int, float)) else v


def schema(request, form, instance=None) -> list:
    out = []
    for name, f in form.fields.items():
        kind = _kind(f)
        item = {'name': name, 'label': str(f.label or name), 'kind': kind, 'required': f.required,
                'help': str(f.help_text or ''), 'max_length': getattr(f, 'max_length', None)}
        if kind == 'choice':
            # у ModelChoiceField ключ — обёртка с .value; названия из базы (категории) — через перевод
            item['choices'] = [{'key': _value(getattr(k, 'value', k)), 'name': _(str(v))}
                               for k, v in f.choices if getattr(k, 'value', k) not in ('', None)]
        if instance is not None:
            val = getattr(instance, name, None)
            item['value'] = file_url(request, val) if kind in ('image', 'file') else _value(val)
        elif f.initial is not None:
            item['value'] = _value(f.initial)
        out.append(item)
    return out


@api(auth=True)
def form_schema(request, key):
    pub = _pub(key)
    obj = None
    pk = request.GET.get('id')
    if pk:
        obj = get_object_or_404(pub.get_model(), pk=pk, **{pub.owner: request.user})
    form = pub.get_form()(instance=obj)
    price = SiteSettings.get_solo().doctor_publish_price if key == 'doctors' and obj is None else 0
    return {'key': key, 'title': str(pub.label), 'fields': schema(request, form, obj), 'editing': obj is not None,
            'pledge': [str(x) for x in PLEDGE] if obj is None else [], 'price': price,
            'geo': 'lat' in form.fields}


@api(methods=('POST',), auth=True)
def save(request, key):
    """Создать (с договором автора) или изменить свою публикацию. После правки — снова на проверку."""
    pub = _pub(key)
    model = pub.get_model()
    pk = request.data.get('id')
    obj = get_object_or_404(model, pk=pk, **{pub.owner: request.user}) if pk else None
    if obj is None:
        limit_key = f'publish:{request.user.pk}'      # тот же счётчик, что на сайте
        if cache.get(limit_key, 0) >= PUBLISH_PER_DAY and not request.user.is_staff:
            raise ApiError(_('На сегодня лимит публикаций исчерпан — защита от спама. Завтра можно снова.'), 429, 'limit')
        if str(request.data.get('pledge', '')) not in ('1', 'true'):
            raise ApiError(_('Чтобы опубликовать, примите договор автора внизу формы.'), 400, 'pledge')
        cache.set(limit_key, cache.get(limit_key, 0) + 1, 86400)
    form = pub.get_form()(request.data, request.FILES, instance=obj)
    if not form.is_valid():
        from django.http import JsonResponse
        errors = {k: ' '.join(str(x) for x in v) for k, v in form.errors.items()}
        return JsonResponse({'error': next(iter(errors.values())), 'fields': errors}, status=400)
    item = form.save(commit=False)
    setattr(item, pub.owner, request.user)
    st = SiteSettings.get_solo()
    if hasattr(item, 'status'):
        item.status = Moderation.PENDING
        if key == 'buy' and obj is None and not st.market_moderation:
            item.status = Moderation.APPROVED          # маркет без модерации (настройка админа)
    if key == 'doctors' and obj is None and st.doctor_publish_price:
        from apps.wallet import services as wallet
        from apps.wallet.models import Transaction
        try:
            wallet.debit(request.user, st.doctor_publish_price, Transaction.PURCHASE, ref='health:doctor',
                         note='Публикация врача')
        except wallet.InsufficientFunds:
            raise ApiError(_('Недостаточно средств для платной публикации.'), 402, 'money') from None
    item.save()
    form.save_m2m()
    if obj is None:
        log_action(request, 'Принят договор автора (приложение)', f'/{key}/')
    log_action(request, f'{"Изменена" if obj else "Создана"} публикация в приложении ({pub.label})', f'{key}#{item.pk}')
    published = getattr(item, 'status', Moderation.APPROVED) == Moderation.APPROVED
    return {'ok': True, 'id': item.pk, 'status': getattr(item, 'status', ''),
            'message': _('Опубликовано!') if published else _('Отправлено на модерацию. Обычно это до суток.')}


@api(auth=True)
def my(request):
    groups = []
    for pub in PUBLICATIONS:
        if not module_on(MODULE_OF.get(pub.key, pub.key)):
            continue
        items = []
        for obj in pub.get_model().objects.filter(**{pub.owner: request.user}).order_by('-pk')[:100]:
            status = getattr(obj, 'status', '')
            hidden = bool(pub.active and not getattr(obj, pub.active))
            items.append({'id': obj.pk, 'title': pub.title_of(obj), 'status': status,
                          'status_name': str(_('Скрыто вами') if hidden else STATUS.get(status, '')),
                          'hidden': hidden, 'public': not hidden and status == Moderation.APPROVED,
                          'can_edit': bool(pub.form), 'can_hide': bool(pub.active)})
        if items:
            groups.append({'key': pub.key, 'title': str(pub.label), 'items': items})
    create = [{'key': p.key, 'title': str(p.label), 'native': bool(p.form), 'web': p.create}
              for p in PUBLICATIONS if p.create and module_on(MODULE_OF.get(p.key, p.key))]
    return {'groups': groups, 'create': create}


@api(methods=('POST', 'DELETE'), auth=True)
def my_item(request, key, pk):
    pub = BY_KEY.get(key)
    if pub is None:
        raise Http404
    obj = get_object_or_404(pub.get_model(), pk=pk, **{pub.owner: request.user})
    if request.method == 'DELETE':
        title = pub.title_of(obj)
        obj.delete()
        log_action(request, f'Удалена публикация в приложении ({pub.label})', f'{key}#{pk}: {title}'[:200])
        return {'ok': True}
    if not pub.active:
        raise ApiError(_('Эту публикацию нельзя скрыть — только удалить.'))
    setattr(obj, pub.active, not getattr(obj, pub.active))
    obj.save(update_fields=[pub.active])
    return {'ok': True, 'hidden': not getattr(obj, pub.active)}
