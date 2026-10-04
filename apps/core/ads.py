"""Реклама — по образцу Telegram Ads: короткое объявление с пометкой «Реклама», без слежки за человеком.

Правила (они же — обещание пользователям):
* показывается только в общих местах: внизу открытых каналов, карточкой в ленте, плиткой на главной;
  в личных чатах, группах, сообществах, никяхе и на страницах оплаты рекламы нет;
* выбор объявления не зависит от того, кто смотрит: переписка, интересы и поиск не используются — только место показа;
* объявления добавляет владелец площадки (Админка → «Реклама») и сам отвечает, что товар и услуга дозволены;
* считаются только показы и переходы — сколько, а не чьи.

Дальше (не сделано): покупка рекламы самим рекламодателем из кошелька, выбор конкретных каналов и городов,
доля дохода владельцу канала (в Telegram — 50%), отключение рекламы платной подпиской.
"""
import random

from django.core.cache import cache
from django.db.models import F, Q
from django.utils import timezone

PLACES = {'channel': 'in_channels', 'feed': 'in_feed', 'home': 'in_home'}


def _active() -> list:
    """Все идущие сейчас объявления (из кеша на минуту — спрашивают на каждой странице ленты и канала)."""
    from .models import Ad
    rows = cache.get('ads:active')
    if rows is None:
        now = timezone.now()
        rows = [{'id': a.pk, 'title': a.title, 'text': a.text, 'button': a.button, 'image': a.image.url if a.image else '',
                 'in_channels': a.in_channels, 'in_feed': a.in_feed, 'in_home': a.in_home}
                for a in Ad.objects.filter(is_active=True).filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
                .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))[:50]]
        cache.set('ads:active', rows, 60)
    return rows


def pick(place: str, count: bool = True) -> dict | None:
    """Одно объявление для места показа ('channel' | 'feed' | 'home') или None. Засчитывает показ."""
    from .models import Ad
    field = PLACES.get(place)
    rows = [a for a in _active() if field and a[field]]
    if not rows:
        return None
    ad = random.choice(rows)
    if count:
        Ad.objects.filter(pk=ad['id']).update(impressions=F('impressions') + 1)
    return {'id': ad['id'], 'title': ad['title'], 'text': ad['text'], 'button': ad['button'], 'image': ad['image'], 'url': f"/ad/{ad['id']}/"}


def for_thread(thread) -> dict | None:
    """Реклама в чате — только в открытом канале (не в сообществе): как спонсорские сообщения Telegram."""
    if thread is None or not getattr(thread, 'is_channel', False) or not thread.is_public or getattr(thread, 'space_id', None):
        return None
    return pick('channel')


def click(ad_id) -> str:
    """Переход по объявлению: засчитать и вернуть настоящий адрес ('' — объявления уже нет)."""
    from .models import Ad
    ad = Ad.objects.filter(pk=ad_id, is_active=True).first()
    if ad is None:
        return ''
    Ad.objects.filter(pk=ad.pk).update(clicks=F('clicks') + 1)
    return ad.url
