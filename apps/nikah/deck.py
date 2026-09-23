"""Лента-колода никяха: какие анкеты показать, дневной лимит, фильтры, премиум.

Свайп вправо — интерес (services.send_interest), влево — пропуск (NikahSkip).
Без премиума — не больше SiteSettings.nikah_daily_limit решений в сутки.
Фильтры хранятся в сессии (переживают перезагрузку, не светятся в адресе).
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import Moderation, SiteSettings

from .models import NikahInterest, NikahMatch, NikahProfile, NikahSkip
from .services import compatibility

SESSION_KEY = 'nikah_filters'
DECK_SIZE = 12
ONLINE_TOUCH = timedelta(minutes=3)

# Группы национальностей для фильтра: поиск по началу слова в свободном поле «национальность»
NATION_GROUPS = [
    ('caucasus', 'Кавказ', ['чечен', 'ингуш', 'дагест', 'авар', 'даргин', 'лезгин', 'кумык', 'лак', 'табасаран',
                            'кабардин', 'балкар', 'карачаев', 'черкес', 'адыг', 'осетин', 'азербайдж']),
    ('central_asia', 'Средняя Азия', ['узбек', 'казах', 'кыргыз', 'киргиз', 'таджик', 'туркмен', 'каракалпак',
                                      'уйгур']),
    ('turkic', 'Тюрки', ['татар', 'башкир', 'турок', 'турчан', 'турец', 'азербайдж', 'гагауз', 'ногай', 'кумык',
                         'крымск', 'чуваш']),
    ('arab', 'Арабы', ['араб', 'египт', 'сири', 'иордан', 'палестин', 'ливан', 'ирак', 'марокк', 'алжир', 'тунис',
                       'саудов', 'йемен', 'ливи', 'судан']),
    ('south_asia', 'Южная Азия', ['пакистан', 'инди', 'бенгал', 'бангладеш', 'афган', 'пуштун', 'хазар']),
]

RANGES = {'age': (18, 80), 'height': (120, 230), 'weight': (40, 200)}
CHOICE_FILTERS = ('madhhab', 'aqida', 'prayer', 'ready_when', 'marital', 'look', 'children_want', 'relocation')
TOGGLES = ('with_photo', 'online', 'no_children', 'never_married', 'polygyny')


def settings_():
    return SiteSettings.get_solo()


# ---------- фильтры ----------

def clean_filters(data) -> dict:
    """Из формы (POST) — в словарь для сессии: только допустимые значения."""
    f = {}
    for field in ('country', 'city', 'nation_text'):
        value = (data.get(field) or '').strip()[:60]
        if value:
            f[field] = value
    group = data.get('nation_group', '')
    if group in {g for g, _l, _k in NATION_GROUPS}:
        f['nation_group'] = group
    for name, (lo, hi) in RANGES.items():
        try:
            a, b = int(data.get(f'{name}_min', lo)), int(data.get(f'{name}_max', hi))
        except (TypeError, ValueError):
            continue
        a, b = max(lo, min(a, hi)), max(lo, min(b, hi))
        if a > b:
            a, b = b, a
        if (a, b) != (lo, hi):
            f[name] = [a, b]
    for field in CHOICE_FILTERS:
        value = (data.get(field) or '').strip()
        if value:
            f[field] = value[:12]
    for t in TOGGLES:
        if data.get(t) == '1':
            f[t] = True
    return f


def apply_filters(qs, f: dict, me: NikahProfile):
    if f.get('country'):
        qs = qs.filter(country__icontains=f['country'])
    if f.get('city'):
        qs = qs.filter(city__icontains=f['city'])
    if f.get('nation_text'):
        qs = qs.filter(nationality__icontains=f['nation_text'])
    if f.get('nation_group'):
        words = next((k for g, _l, k in NATION_GROUPS if g == f['nation_group']), [])
        cond = Q()
        for w in words:
            cond |= Q(nationality__icontains=w)
        qs = qs.filter(cond)
    for name in RANGES:
        if name in f:
            a, b = f[name]
            qs = qs.filter(**{f'{name}__gte': a, f'{name}__lte': b})
    for field in CHOICE_FILTERS:
        if f.get(field):
            qs = qs.filter(**{field: f[field]})
    if f.get('with_photo'):
        qs = qs.filter(photo_mode='exchange').exclude(photo_private='')
    if f.get('online') and me.is_premium:
        qs = qs.filter(last_seen__gte=timezone.now() - timedelta(minutes=10))
    if f.get('no_children'):
        qs = qs.filter(has_children='no')
    if f.get('never_married'):
        qs = qs.filter(marital='never')
    if f.get('polygyny') and me.gender == 'M':
        qs = qs.filter(polygyny__in=['yes', 'discuss'])
    return qs


# ---------- колода и лимит ----------

def used_today(me: NikahProfile) -> int:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return (NikahSkip.objects.filter(from_profile=me, created_at__gte=start).count()
            + NikahInterest.objects.filter(from_profile=me, created_at__gte=start).count())


def left_today(me: NikahProfile) -> int | None:
    """Сколько решений осталось сегодня. None — без ограничения (премиум)."""
    if me.is_premium:
        return None
    return max(0, settings_().nikah_daily_limit - used_today(me))


def candidates(me: NikahProfile, f: dict):
    decided = list(NikahSkip.objects.filter(from_profile=me).values_list('to_profile_id', flat=True))
    decided += list(NikahInterest.objects.filter(from_profile=me).values_list('to_profile_id', flat=True))
    matched = NikahMatch.objects.filter(Q(sister=me) | Q(brother=me)).values_list('sister_id', 'brother_id')
    decided += [x for pair in matched for x in pair]
    qs = (NikahProfile.objects.filter(status=Moderation.APPROVED, is_active=True)
          .exclude(gender=me.gender).exclude(pk=me.pk).exclude(pk__in=decided))
    return apply_filters(qs, f, me)


def deck(me: NikahProfile, f: dict) -> list:
    """Анкеты для колоды: сначала поднятые, затем по совместимости."""
    left = left_today(me)
    if left == 0:
        return []
    profiles = list(candidates(me, f)[:300])
    for p in profiles:
        p.compat, p.why = compatibility(me, p)
    profiles.sort(key=lambda p: (not p.is_boosted, -p.compat))
    size = DECK_SIZE if left is None else min(DECK_SIZE, left)
    return profiles[:size]


def skip(me: NikahProfile, other: NikahProfile) -> None:
    NikahSkip.objects.get_or_create(from_profile=me, to_profile=other)


def skipped_count(me: NikahProfile) -> int:
    return NikahSkip.objects.filter(from_profile=me).count()


@transaction.atomic
def restore_skipped(me: NikahProfile, user) -> int:
    """«Вернуть отклонённых» — платно, с премиумом бесплатно."""
    from apps.wallet import services as wallet
    from apps.wallet.models import Transaction

    n = skipped_count(me)
    if not n:
        return 0
    price = settings_().nikah_restore_price
    if price and not me.is_premium:
        wallet.debit(user, price, Transaction.PURCHASE, ref='nikah:restore', note='Никях: вернуть отклонённых')
    NikahSkip.objects.filter(from_profile=me).delete()
    return n


@transaction.atomic
def buy_premium(me: NikahProfile, user) -> None:
    from apps.wallet import services as wallet
    from apps.wallet.models import Transaction

    st = settings_()
    if not st.nikah_premium_enabled:
        raise ValueError('Премиум сейчас недоступен')
    wallet.debit(user, st.nikah_premium_price, Transaction.PURCHASE, ref='nikah:premium',
                 note=f'Никях: премиум на {st.nikah_premium_days} дней')
    base = me.premium_until if me.is_premium else timezone.now()
    me.premium_until = base + timedelta(days=st.nikah_premium_days)
    me.save(update_fields=['premium_until'])


def touch(me: NikahProfile) -> None:
    """«Был(а) в сети» — пишем не чаще раза в 3 минуты."""
    now = timezone.now()
    if not me.last_seen or now - me.last_seen > ONLINE_TOUCH:
        NikahProfile.objects.filter(pk=me.pk).update(last_seen=now)
        me.last_seen = now
