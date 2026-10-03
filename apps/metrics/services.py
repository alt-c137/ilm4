"""Сбор и сводки аналитики использования (см. models.py). Сводки — для страницы владельца /moderation/stats/."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, F, Sum
from django.utils import timezone

from .models import Use

User = get_user_model()
MAX_BEAT = 90                 # секунд за один «пульс» клиента — больше не засчитываем (защита от накрутки)
MAX_DAY = 16 * 3600
EXTRA = ('home', 'catalog', 'profile', 'settings', 'search', 'notifications', 'my', 'other')


def sections() -> set:
    from apps.core.models import ModuleConfig
    return set(ModuleConfig.objects.values_list('key', flat=True)) | set(EXTRA)


def record(user, anon: str, section: str, seconds, opens, platform: str = Use.WEB) -> None:
    """Засчитать время в разделе. Неизвестный раздел → 'other'; гость считается по случайному номеру из куки."""
    section = section if section in sections() else 'other'
    try:
        seconds, opens = max(0, min(int(seconds or 0), MAX_BEAT)), 1 if str(opens) in ('1', 'true', 'True') else 0
    except (TypeError, ValueError):
        return
    if not seconds and not opens:
        return
    uid = user if getattr(user, 'is_authenticated', False) else None
    key = {'user': uid, 'anon': '' if uid else (anon or '')[:16], 'day': timezone.localdate(), 'section': section,
           'platform': platform if platform in (Use.WEB, Use.APP) else Use.WEB}
    if uid is None and not key['anon']:
        return
    row, _new = Use.objects.get_or_create(**key)
    if row.seconds < MAX_DAY:
        Use.objects.filter(pk=row.pk).update(seconds=F('seconds') + seconds, opens=F('opens') + opens)


def _active(day_from, day_to=None) -> int:
    qs = Use.objects.filter(day__gte=day_from, user__isnull=False)
    if day_to:
        qs = qs.filter(day__lte=day_to)
    return qs.values('user').distinct().count()


def summary(days: int = 30) -> dict:
    """Всё для страницы владельца: активность, возвращаемость, разделы, интересы."""
    today = timezone.localdate()
    since = today - timedelta(days=days - 1)
    uses = Use.objects.filter(day__gte=since)
    total_sec = uses.aggregate(s=Sum('seconds'))['s'] or 0
    active = uses.filter(user__isnull=False).values('user').distinct().count()
    rows = []
    for r in (uses.values('section').annotate(users=Count('user', distinct=True), guests=Count('anon', distinct=True),
                                              opens=Sum('opens'), sec=Sum('seconds')).order_by('-sec')):
        rows.append({'section': r['section'], 'users': r['users'], 'opens': r['opens'] or 0, 'minutes': round((r['sec'] or 0) / 60),
                     'share': round(100 * (r['sec'] or 0) / total_sec) if total_sec else 0,
                     'reach': round(100 * r['users'] / active) if active else 0,
                     'per_user': round((r['sec'] or 0) / 60 / r['users'], 1) if r['users'] else 0})
    used = {r['section'] for r in rows}
    from apps.core.models import ModuleConfig
    unused = [m.name for m in ModuleConfig.objects.filter(status='on') if m.key not in used]
    # по дням: активные люди и минуты
    by_day = {d['day']: d for d in uses.values('day').annotate(users=Count('user', distinct=True), sec=Sum('seconds'))}
    joined = dict(User.objects.filter(date_joined__date__gte=since).values_list('date_joined__date').annotate(n=Count('id')).values_list('date_joined__date', 'n'))
    daily = []
    for i in range(min(days, 30)):
        d = today - timedelta(days=min(days, 30) - 1 - i)
        row = by_day.get(d, {})
        daily.append({'day': d, 'users': row.get('users', 0), 'minutes': round((row.get('sec') or 0) / 60), 'new': joined.get(d, 0)})
    peak = max((x['users'] for x in daily), default=0) or 1
    for x in daily:
        x['bar'] = round(100 * x['users'] / peak)
    return {'days': days, 'dau': _active(today), 'wau': _active(today - timedelta(days=6)), 'mau': _active(today - timedelta(days=29)),
            'users_total': User.objects.filter(is_active=True).count(), 'active': active,
            'minutes_per_user_day': round(total_sec / 60 / max(1, uses.filter(user__isnull=False).values('user', 'day').distinct().count()), 1),
            'sections': rows, 'unused': unused, 'daily': daily, 'retention': retention(), 'interests': interests(since),
            'platforms': {p['platform']: round((p['s'] or 0) / 60) for p in uses.values('platform').annotate(s=Sum('seconds'))}}


def retention() -> list:
    """Возвращаемость: из зарегистрировавшихся — сколько были на 1-й, 7-й, 30-й день (и «хотя бы раз за неделю»)."""
    today = timezone.localdate()
    out = []
    for label, n in (('1', 1), ('7', 7), ('30', 30)):
        cohort = list(User.objects.filter(date_joined__date__lte=today - timedelta(days=n), date_joined__date__gte=today - timedelta(days=n + 60))
                      .values_list('pk', 'date_joined'))
        back = 0
        if cohort:
            days = {}
            for uid, joined in cohort:
                days.setdefault(timezone.localtime(joined).date() + timedelta(days=n), []).append(uid)
            for day, ids in days.items():
                back += Use.objects.filter(day=day, user__in=ids).values('user').distinct().count()
        out.append({'day': label, 'cohort': len(cohort), 'back': back, 'rate': round(100 * back / len(cohort)) if cohort else None})
    return out


def interests(since) -> dict:
    """Что людям интересно: чему ставят лайки, что сохраняют и репостят (по видам карточек ленты)."""
    try:
        from apps.social.models import Like, Post, Saved
    except ImportError:
        return {}
    kinds = {}
    for target, n in Like.objects.filter(created_at__date__gte=since).values_list('target').annotate(n=Count('id')):
        kind = target.split(':', 1)[0]
        kinds[kind] = kinds.get(kind, 0) + n
    return {'likes': sorted(kinds.items(), key=lambda x: -x[1])[:8],
            'saves': Saved.objects.filter(created_at__date__gte=since).count(),
            'reposts': Post.objects.filter(created_at__date__gte=since, repost_of__isnull=False).count(),
            'posts': Post.objects.filter(created_at__date__gte=since, repost_of__isnull=True).count()}
