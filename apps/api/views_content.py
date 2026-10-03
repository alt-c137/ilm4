"""API: новости и публикации разделов (объявления, вакансии, услуги, перевозки, места,
врачи, истории, книги, форум) — одним механизмом: список с поиском и карточка."""
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field

from django.apps import apps
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from apps.core.models import Moderation

from .base import MODULE_OF, ApiError, abs_url, api, file_url, module_on, page

# текущий запрос — чтобы показать «≈» в валюте того, кто смотрит (apps/core/money.py)
_REQ: ContextVar = ContextVar('api_request', default=None)


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
    scope: Callable | None = None                   # доп. отбор, зависящий от времени (поездки — только будущие)


def _price(o):
    from apps.core import money
    return money.price_text(o.price, o.currency, _REQ.get(), _('Даром'))


def _trip_when(o):
    return o.departs_local.strftime('%d.%m %H:%M')


def _trip_seats(o):
    if not o.is_driver:
        return _('ищу машину · нас: {n}').format(n=o.seats)
    return _('мест: {n}').format(n=o.seats_left) if o.seats_left else _('мест нет')


def _trip_price(o):
    from apps.core import money
    return money.price_text(o.price, o.currency, _REQ.get(), _('Бесплатно'))


def _trips_scope(qs):
    from datetime import timedelta

    from django.utils import timezone
    return qs.filter(is_active=True, departs_at__gte=timezone.now() - timedelta(hours=1))


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
    'trips': Kind('transport.Trip', lambda o: f'{o.from_city} → {o.to_city}',
                  lambda o: ' · '.join(x for x in (_trip_when(o), _trip_seats(o), _trip_price(o)) if x),
                  text='comment', contact='', category='role', search=('from_city', 'to_city', 'via', 'comment'),
                  order=('departs_at',), web='/transport/trips/{pk}/', scope=_trips_scope,
                  fields=[(_lazy('Выезд'), _trip_when), (_lazy('Откуда'), _attr('from_city')), (_lazy('Куда'), _attr('to_city')),
                          (_lazy('По пути'), _attr('via')), (_lazy('Места'), _trip_seats),
                          (_lazy('Переднее место'), lambda o: _('свободно') if o.front_seat and o.is_driver else ''),
                          (_lazy('Цена за место'), _trip_price), (_lazy('Машина'), _attr('car')),
                          (_lazy('Кого беру'), lambda o: o.get_audience_display() if o.is_driver else ''),
                          (_lazy('Посылки'), lambda o: _('возьму') if o.parcels else '')]),
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
    qs = apps.get_model(k.model).objects.filter(status=Moderation.APPROVED, **k.extra_filter)
    return k.scope(qs) if k.scope else qs


def card(request, key, k: Kind, o) -> dict:
    return {'id': o.pk, 'type': key, 'title': k.title(o), 'subtitle': k.subtitle(o),
            'image': file_url(request, getattr(o, k.image)) if k.image else '',
            'created_at': o.created_at.isoformat(),
            'lat': float(o.lat) if hasattr(o, 'lat') else None, 'lon': float(o.lon) if hasattr(o, 'lon') else None,
            'verified': bool(getattr(o, 'platform_verified', False))}


@api()
def pubs(request, key):
    _REQ.set(request)
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
    if key == 'trips':                              # занятые места — одним запросом на страницу
        from apps.transport.services import with_taken
        data = page(request, qs, lambda o: o)
        data['items'] = [card(request, key, k, o) for o in with_taken(data['items'])]
    else:
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
    _REQ.set(request)
    k = _kind(key)
    if key == 'trips' and request.user.is_authenticated:      # свою поездку автор видит и после выезда
        o = get_object_or_404(apps.get_model(k.model).objects.filter(
            Q(pk__in=_qs(k).values('pk')) | Q(owner=request.user)), pk=pk)
    else:
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
    if key == 'trips':
        data['trip'] = trip_state(request, o)
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


def trip_state(request, trip) -> dict:
    """Места и заявки для экрана поездки: попутчику — его заявка, водителю — все заявки."""
    from apps.transport.models import TripRequest
    user = request.user
    mine = user.is_authenticated and trip.owner_id == user.pk
    data = {'driver': trip.is_driver, 'seats': trip.seats, 'seats_left': trip.seats_left, 'past': trip.is_past,
            'my_request': None, 'requests': []}
    if mine:
        data['requests'] = [{'id': r.pk, 'user_id': r.user_id, 'name': r.user.get_display_name(), 'seats': r.seats,
                             'status': r.status, 'status_name': r.get_status_display()}
                            for r in trip.requests.select_related('user').exclude(status=TripRequest.CANCELLED)]
    elif user.is_authenticated:
        r = trip.requests.filter(user=user).first()
        if r and r.status != TripRequest.CANCELLED:
            data['my_request'] = {'id': r.pk, 'seats': r.seats, 'status': r.status, 'status_name': r.get_status_display()}
    return data


@api(methods=('POST',), auth=True, module='transport')
def trip_request(request, pk):
    """Занять место в поездке."""
    from apps.transport import services as trips
    from apps.transport.models import Trip
    trip = get_object_or_404(Trip, pk=pk)
    try:
        trips.request_seat(trip, request.user, request.data.get('seats'))
    except trips.TripError as exc:
        raise ApiError(exc.message, exc.status) from exc
    trip = Trip.objects.get(pk=pk)
    return {'ok': True, 'trip': trip_state(request, trip)}


@api(methods=('POST',), auth=True, module='transport')
def trip_request_act(request, req_id, action):
    """accept / decline — водитель; cancel — попутчик."""
    from apps.transport import services as trips
    from apps.transport.models import Trip, TripRequest
    req = get_object_or_404(TripRequest.objects.select_related('trip', 'user'), pk=req_id)
    try:
        if action in ('accept', 'decline'):
            trips.answer(req, request.user, action == 'accept')
        elif action == 'cancel':
            trips.cancel(req, request.user)
        else:
            raise ApiError('action', 404)
    except trips.TripError as exc:
        raise ApiError(exc.message, exc.status) from exc
    return {'ok': True, 'trip': trip_state(request, Trip.objects.get(pk=req.trip_id))}


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
    from apps.chat import services as chat
    if not module_on('chat'):
        raise ApiError(_('Раздел сейчас выключен'), 404, 'module_off')
    k = _kind(key)
    o = get_object_or_404(_qs(k), pk=pk)
    owner = getattr(o, k.owner, None) if k.owner else None
    if owner is None or owner == request.user:
        raise ApiError(_('Нельзя написать себе'))
    try:
        thread = chat.open_direct(request.user, owner, k.title(o), context=(key, o.pk))   # свой чат на объявление
    except chat.ChatError as exc:
        raise ApiError(exc.message, exc.status) from exc
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
    text = request.GET.get('q', '').strip()[:60]
    if text:
        from django.db.models import Q
        qs = qs.filter(Q(name__icontains=text) | Q(address__icontains=text) | Q(city__icontains=text))
    from apps.maps.views import ICONS
    out = []
    for p in qs.prefetch_related('confirmations')[:500]:
        v = p.verification()
        if request.GET.get('verified') and v['level'] == 'none':
            continue
        out.append({'id': p.pk, 'name': p.name, 'category': p.category, 'category_name': p.get_category_display(),
                    'lat': float(p.lat), 'lon': float(p.lon), 'verified': p.platform_verified, 'icon': ICONS.get(p.category, 'place'),
                    'address': p.address, 'city': p.city, 'phone': p.phone, 'verif': v['level'], 'verif_label': str(v['label']),
                    'brief': p.mosque_brief() if p.is_mosque else '', 'photo': abs_url(request, p.photo.url) if p.photo else ''})
    return {'items': out, 'categories': [{'key': k, 'name': str(n), 'icon': ICONS.get(k, 'place')} for k, n in HalalPlace.CATEGORIES]}
