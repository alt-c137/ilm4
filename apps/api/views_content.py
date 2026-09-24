"""API: новости и публикации разделов (объявления, вакансии, услуги, перевозки, места,
врачи, истории, книги, форум) — одним механизмом: список с поиском и карточка."""
from collections.abc import Callable
from dataclasses import dataclass, field

from django.apps import apps
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from apps.core.models import Moderation

from .base import MODULE_OF, ApiError, abs_url, api, file_url, module_on, page


def _money(v) -> str:
    return f'{int(v):,}'.replace(',', ' ')


def _disp(name):
    return lambda o: str(getattr(o, f'get_{name}_display')() or '')


def _attr(name):
    return lambda o: str(getattr(o, name) or '')


@dataclass
class Kind:
    model: str
    title: Callable
    subtitle: Callable
    text: str = 'description'
    image: str = ''
    owner: str = 'owner'
    search: tuple = ('title', 'description')
    fields: list = field(default_factory=list)     # [(подпись, функция)]
    contact: str = 'contact'
    category: str = ''                              # поле для фильтра ?category=
    extra_filter: dict = field(default_factory=dict)
    order: tuple = ('-created_at',)
    web: str = ''                                   # адрес на сайте (для «Поделиться»)


def _price(o):
    return _('Даром') if o.price == 0 else f'{_money(o.price)} {o.currency}'


def _book_price(o):
    return _('Бесплатно') if not o.price else f'{_money(o.price)} {_("сум")}'


KINDS = {
    'buy': Kind('market.Listing', _attr('title'), lambda o: ' · '.join(x for x in (_price(o), o.city) if x),
                image='photo', category='category__slug', extra_filter={'is_active': True},
                order=('-boosted_until', '-created_at'), web='/buy/{pk}/',
                fields=[(_lazy('Цена'), _price), (_lazy('Категория'), lambda o: _(o.category.name)),
                        (_lazy('Город'), _attr('city'))]),
    'jobs': Kind('jobs.Vacancy', _attr('title'),
                 lambda o: ' · '.join(x for x in (o.salary, o.company, o.city) if x), category='category',
                 search=('title', 'description', 'company'), web='/jobs/{pk}/',
                 fields=[(_lazy('Тип'), _disp('kind')), (_lazy('Раздел'), _disp('category')),
                         (_lazy('Компания'), _attr('company')), (_lazy('Город'), _attr('city')),
                         (_lazy('Зарплата'), _attr('salary'))]),
    'services': Kind('services.Service', _attr('name'),
                     lambda o: ' · '.join(x for x in (o.get_kind_display(), o.price_text, o.city) if x),
                     category='kind', search=('name', 'description'), web='/services/',
                     fields=[(_lazy('Вид'), _disp('kind')), (_lazy('Цена'), _attr('price_text')),
                             (_lazy('Город'), _attr('city'))]),
    'transport': Kind('transport.Ride', lambda o: f'{o.from_city} → {o.to_city}',
                      lambda o: ' · '.join(x for x in (o.get_type_display(), o.ride_date and o.ride_date.strftime('%d.%m.%Y'),
                                                        o.price_text) if x),
                      category='type', search=('from_city', 'to_city', 'description', 'company'), web='/transport/',
                      fields=[(_lazy('Тип'), _disp('type')), (_lazy('Откуда'), _attr('from_city')),
                              (_lazy('Куда'), _attr('to_city')), (_lazy('Дата'), lambda o: o.ride_date.strftime('%d.%m.%Y') if o.ride_date else ''),
                              (_lazy('Перевозчик'), _attr('company')), (_lazy('Цена'), _attr('price_text'))]),
    'places': Kind('maps.HalalPlace', _attr('name'), lambda o: ' · '.join(x for x in (o.get_category_display(), o.city) if x),
                   image='photo', search=('name', 'description', 'address', 'city'), category='category',
                   contact='phone', web='/map/{pk}/',
                   fields=[(_lazy('Категория'), _disp('category')), (_lazy('Город'), _attr('city')),
                           (_lazy('Адрес'), _attr('address')), (_lazy('Телефон'), _attr('phone')),
                           (_lazy('Сайт'), _attr('url')), (_lazy('Течение'), _disp('branch')),
                           (_lazy('Мазхаб'), _disp('madhhab')), (_lazy('Манхадж'), _disp('manhaj')),
                           (_lazy('На чём держится'), _disp('kind')), (_lazy('Кому принадлежит'), _attr('affiliation')),
                           (_lazy('Имам'), _attr('imam')), (_lazy('Язык хутбы'), _attr('khutba_lang'))]),
    'doctors': Kind('health.Doctor', _attr('name'), lambda o: ' · '.join(x for x in (o.get_category_display(), o.city) if x),
                    image='photo', search=('name', 'description', 'clinic', 'city'), category='category',
                    contact='phone', web='/health/{pk}/',
                    fields=[(_lazy('Специализация'), _disp('category')), (_lazy('Клиника'), _attr('clinic')),
                            (_lazy('Опыт, лет'), lambda o: str(o.experience or '')), (_lazy('Город'), _attr('city')),
                            (_lazy('Адрес'), _attr('address')), (_lazy('Телефон'), _attr('phone'))]),
    'stories': Kind('migration.Story', _attr('title'), lambda o: f'{o.country_from} → {o.country_to}', text='body',
                    owner='author', search=('title', 'body', 'country_to'), contact='', web='/migration/{pk}/',
                    fields=[(_lazy('Откуда'), _attr('country_from')), (_lazy('Куда'), _attr('country_to'))]),
    'books': Kind('library.Book', _attr('title'), lambda o: ' · '.join(x for x in (o.author, _book_price(o)) if x),
                  image='cover', search=('title', 'author', 'description'), category='category', contact='',
                  web='/library/', fields=[(_lazy('Автор'), _attr('author')), (_lazy('Раздел'), _disp('category')),
                                           (_lazy('Цена'), _book_price)]),
    'topics': Kind('forum.Topic', _attr('title'), lambda o: _('Ответов: {n}').format(n=o.replies.count()), text='body',
                   owner='author', search=('title', 'body'), contact='', web='/forum/{pk}/'),
}


def _kind(key) -> Kind:
    k = KINDS.get(key)
    if k is None or not module_on(MODULE_OF[key]):
        from django.http import Http404
        raise Http404
    return k


def _qs(k: Kind):
    return apps.get_model(k.model).objects.filter(status=Moderation.APPROVED, **k.extra_filter)


def card(request, key, k: Kind, o) -> dict:
    return {'id': o.pk, 'type': key, 'title': k.title(o), 'subtitle': k.subtitle(o),
            'image': file_url(request, getattr(o, k.image)) if k.image else '',
            'created_at': o.created_at.isoformat(),
            'lat': float(o.lat) if hasattr(o, 'lat') else None, 'lon': float(o.lon) if hasattr(o, 'lon') else None,
            'verified': bool(getattr(o, 'platform_verified', False))}


@api()
def pubs(request, key):
    k = _kind(key)
    qs = _qs(k)
    q = request.GET.get('q', '').strip()[:100]
    if q:
        cond = Q()
        for f in k.search:
            cond |= Q(**{f'{f}__icontains': q})
        qs = qs.filter(cond)
    city = request.GET.get('city', '').strip()[:80]
    if city and hasattr(qs.model, 'city'):
        qs = qs.filter(city__icontains=city)
    cat = request.GET.get('category', '').strip()[:40]
    if cat and k.category:
        qs = qs.filter(**{k.category: cat})
    if request.user.is_authenticated and k.owner:
        from apps.accounts.models import UserBlock
        blocked = UserBlock.ids_for(request.user)
        if blocked:
            qs = qs.exclude(**{f'{k.owner}_id__in': blocked})
    qs = qs.order_by(*k.order)
    if k.owner:
        qs = qs.select_related(k.owner)
    data = page(request, qs, lambda o: card(request, key, k, o))
    if request.GET.get('page', '1') == '1':
        data['categories'] = _categories(key, k)
    return data


def _categories(key, k: Kind) -> list:
    if not k.category:
        return []
    if key == 'buy':
        from apps.market.models import Category
        return [{'key': c.slug, 'name': _(c.name), 'emoji': c.icon} for c in Category.objects.all()]
    model = apps.get_model(k.model)
    f = model._meta.get_field(k.category)
    return [{'key': v, 'name': str(label)} for v, label in (f.choices or [])]


@api()
def pub_detail(request, key, pk):
    k = _kind(key)
    o = get_object_or_404(_qs(k), pk=pk)
    owner = getattr(o, k.owner, None) if k.owner else None
    data = card(request, key, k, o)
    data.update({
        'text': getattr(o, k.text, '') or '',
        'fields': [{'label': str(label), 'value': v} for label, fn in k.fields if (v := fn(o))],
        'contact': getattr(o, k.contact, '') if k.contact else '',
        'owner': {'id': owner.pk, 'name': owner.get_display_name()} if owner else None,
        'mine': bool(owner and request.user.is_authenticated and owner.pk == request.user.pk),
        'can_message': bool(owner and module_on('chat') and not (request.user.is_authenticated and owner.pk == request.user.pk)),
        'url': abs_url(request, k.web.format(pk=o.pk)) if k.web else '',
    })
    if key == 'buy':
        from django.db.models import F
        type(o).objects.filter(pk=o.pk).update(views=F('views') + 1)
    if key == 'topics':
        data['replies'] = [{'id': r.pk, 'text': r.body, 'author': r.author.get_display_name(),
                            'created_at': r.created_at.isoformat()}
                           for r in o.replies.select_related('author').order_by('created_at')[:200]]
    if key == 'places':
        data['features'] = [str(label) for flag, label in (
            ('has_jumua', _lazy('Джума-намаз')), ('has_women', _lazy('Женский зал')),
            ('has_wudu', _lazy('Место для омовения')), ('has_parking', _lazy('Парковка')),
            ('accessible', _lazy('Доступно для колясок'))) if getattr(o, flag, False)]
    return data


@api(methods=('POST',), auth=True, module='forum')
def topic_reply(request, pk):
    from apps.forum.models import Reply, Topic

    from .base import limit
    topic = get_object_or_404(Topic, pk=pk, status=Moderation.APPROVED)
    body = str(request.data.get('text', '')).strip()
    if not 2 <= len(body) <= 5000:
        raise ApiError(_('Напишите ответ.'))
    limit(f'api_reply:{request.user.pk}', 30, 3600)
    r = Reply.objects.create(topic=topic, author=request.user, body=body)
    return {'id': r.pk, 'text': r.body, 'author': request.user.get_display_name(), 'created_at': r.created_at.isoformat()}


@api(methods=('POST',), auth=True)
def pub_message(request, key, pk):
    """«Написать автору»: открыть (или найти) диалог — как кнопка на сайте."""
    from apps.chat.models import Thread
    if not module_on('chat'):
        raise ApiError(_('Раздел сейчас выключен'), 404, 'module_off')
    k = _kind(key)
    o = get_object_or_404(_qs(k), pk=pk)
    owner = getattr(o, k.owner, None) if k.owner else None
    if owner is None or owner == request.user:
        raise ApiError(_('Нельзя написать себе'))
    from apps.accounts.models import UserBlock
    if UserBlock.between(request.user, owner):
        raise ApiError(_('Переписка недоступна: блокировка'), 403)
    subject = k.title(o)[:160]
    thread = (Thread.objects.filter(kind=Thread.DIRECT, participants=request.user).filter(participants=owner)
              .exclude(observers__isnull=False).first())
    if thread is None:
        thread = Thread.objects.create(subject=subject)
        thread.participants.add(request.user, owner)
    elif thread.subject != subject:
        thread.subject = subject
        thread.save(update_fields=['subject', 'updated_at'])
    return {'thread_id': thread.pk}


# ---------- новости ----------

def news_card(request, n) -> dict:
    return {'id': n.pk, 'title': n.title, 'summary': n.summary, 'image': file_url(request, n.cover),
            'pinned': n.is_pinned, 'created_at': n.created_at.isoformat()}


@api(module='news')
def news(request):
    from apps.news.models import NewsPost
    qs = NewsPost.objects.order_by('-is_pinned', '-created_at')
    q = request.GET.get('q', '').strip()[:100]
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))
    return page(request, qs, lambda n: news_card(request, n))


@api(module='news')
def news_detail(request, pk):
    from apps.news.models import NewsPost
    n = get_object_or_404(NewsPost, pk=pk)
    return {**news_card(request, n), 'text': n.body, 'url': abs_url(request, f'/news/{n.slug}/')}


# ---------- карта: места в видимой области ----------

@api(module='map')
def places_map(request):
    from apps.maps.models import HalalPlace
    try:
        s, w, n, e = (float(x) for x in request.GET.get('bbox', '').split(','))
    except ValueError:
        raise ApiError('bbox') from None
    qs = HalalPlace.objects.filter(status=Moderation.APPROVED, lat__gte=s, lat__lte=n, lon__gte=w, lon__lte=e)
    cat = request.GET.get('category', '')
    if cat:
        qs = qs.filter(category=cat)
    return {'items': [{'id': p.pk, 'name': p.name, 'category': p.category, 'category_name': p.get_category_display(),
                       'lat': float(p.lat), 'lon': float(p.lon), 'verified': p.platform_verified}
                      for p in qs[:500]]}
