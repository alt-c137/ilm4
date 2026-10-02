"""Попутчики: поиск поездок и заявки на места — общее для сайта и приложения."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.models import Moderation, Notification

from .models import Trip, TripRequest


class TripError(Exception):
    def __init__(self, message, status=400):
        super().__init__(str(message))
        self.message, self.status = str(message), status


def upcoming():
    """Опубликованные поездки, которые ещё не уехали (час после выезда ещё показываем — вдруг задержались)."""
    return Trip.objects.filter(status=Moderation.APPROVED, is_active=True,
                               departs_at__gte=timezone.now() - timedelta(hours=1))


def search(qs, f_from='', f_to='', day=None, role='', audience=''):
    """Откуда/куда ищем и в «по пути»: Джидда найдётся в поездке Мекка → Медина через Джидду."""
    if f_from:
        qs = qs.filter(Q(from_city__icontains=f_from) | Q(via__icontains=f_from))
    if f_to:
        qs = qs.filter(Q(to_city__icontains=f_to) | Q(via__icontains=f_to))
    if day:                                            # сутки с запасом на разницу поясов
        from datetime import datetime, time
        start = timezone.make_aware(datetime.combine(day, time.min)) - timedelta(hours=6)
        qs = qs.filter(departs_at__gte=start, departs_at__lt=start + timedelta(hours=36))
    if role in dict(Trip.ROLES):
        qs = qs.filter(role=role)
    if audience in dict(Trip.AUDIENCE):
        qs = qs.filter(audience=audience)
    return qs


def with_taken(trips):
    """Проставить занятые места одним запросом на весь список."""
    trips = list(trips)
    taken = dict(TripRequest.objects.filter(trip__in=trips, status=TripRequest.ACCEPTED)
                 .values_list('trip').annotate(n=Sum('seats')))
    for t in trips:
        t._taken = taken.get(t.pk, 0)
    return trips


def _say(sender, trip, other, text):
    """Сообщение в чат этой поездки (свой чат на каждую поездку); чат выключен — уведомление."""
    from apps.chat import services as chat
    from apps.core.models import ModuleConfig
    if ModuleConfig.objects.filter(key='chat', status=ModuleConfig.ON).exists():
        try:
            # чат открывает попутчик (тот, кто не автор): контекст привязан к автору поездки
            guest = other if sender.pk == trip.owner_id else sender
            thread = chat.open_direct(guest, trip.owner, context=('trips', trip.pk))
            chat.send_text(thread, sender, text)
            return thread
        except chat.ChatError:
            pass
    Notification.objects.create(user=other, text=f'{sender.get_display_name()}: {text}'[:300],
                                url=f'/transport/trips/{trip.pk}/')
    return None


def request_seat(trip, user, seats=1) -> TripRequest:
    try:
        seats = max(1, min(int(seats or 1), 8))
    except (TypeError, ValueError):
        seats = 1
    if trip.owner_id == user.pk:
        raise TripError(_('Это ваша поездка.'))
    if not trip.is_driver:
        raise TripError(_('Здесь ищут машину — напишите автору.'))
    if trip.status != Moderation.APPROVED or not trip.is_active or trip.is_past:
        raise TripError(_('Поездка уже недоступна.'), 404)
    with transaction.atomic():
        trip = Trip.objects.select_for_update().get(pk=trip.pk)
        if seats > trip.seats_left:
            raise TripError(_('Свободных мест: {n}').format(n=trip.seats_left))
        req, created = TripRequest.objects.get_or_create(trip=trip, user=user, defaults={'seats': seats})
        if not created:
            if req.status in (TripRequest.PENDING, TripRequest.ACCEPTED):
                raise TripError(_('Вы уже подали заявку на эту поездку.'))
            req.seats, req.status = seats, TripRequest.PENDING          # после отказа/отмены можно попросить снова
            req.save(update_fields=['seats', 'status'])
    _say(user, trip, trip.owner, _('Ассаляму алейкум! Хочу поехать с вами: {route}, мест — {n}.')
         .format(route=f'{trip.from_city} → {trip.to_city}', n=seats))
    return req


def answer(req, owner, accept: bool) -> TripRequest:
    """Водитель подтверждает или отказывает."""
    if req.trip.owner_id != owner.pk:
        raise TripError(_('Нет доступа'), 403)
    with transaction.atomic():
        trip = Trip.objects.select_for_update().get(pk=req.trip_id)
        req = TripRequest.objects.select_for_update().get(pk=req.pk)
        if req.status != TripRequest.PENDING:
            raise TripError(_('Заявка уже обработана.'))
        if accept and req.seats > trip.seats_left:
            raise TripError(_('Свободных мест: {n}').format(n=trip.seats_left))
        req.status = TripRequest.ACCEPTED if accept else TripRequest.DECLINED
        req.save(update_fields=['status'])
    when = trip.departs_local.strftime('%d.%m %H:%M')
    _say(owner, trip, req.user, _('Место за вами: {n}. Выезд {when}.').format(n=req.seats, when=when) if accept
         else _('К сожалению, взять вас не получится.'))
    return req


def cancel(req, user) -> TripRequest:
    """Попутчик передумал — место освобождается."""
    if req.user_id != user.pk:
        raise TripError(_('Нет доступа'), 403)
    if req.status not in (TripRequest.PENDING, TripRequest.ACCEPTED):
        raise TripError(_('Заявка уже закрыта.'))
    was_accepted = req.status == TripRequest.ACCEPTED
    req.status = TripRequest.CANCELLED
    req.save(update_fields=['status'])
    if was_accepted:
        _say(user, req.trip, req.trip.owner, _('Я не смогу поехать — место свободно.'))
    return req
