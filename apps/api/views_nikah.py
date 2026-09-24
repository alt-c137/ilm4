"""API никяха: анкета (создание и правка), колода, интерес/пропуск, интересы, пары, обмен фото.

Логика та же, что на сайте (apps/nikah: deck, services, forms) — здесь только JSON.
Фото пары отдаются с водяным знаком и только в свою очередь, пока идёт таймер;
в приложении экран фото защищён от скриншотов (Android) и записи экрана.
"""
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from apps.accounts.audit import log_action
from apps.core.models import Moderation, SiteSettings
from apps.nikah import choices as C
from apps.nikah import deck, services
from apps.nikah.forms import NikahProfileForm
from apps.nikah.models import NikahInterest, NikahMatch, NikahProfile, NikahSaved
from apps.wallet.services import InsufficientFunds, balance_of

from .base import ApiError, abs_url, api

NO_MONEY = _lazy('На балансе не хватает средств — пополните кошелёк.')


def _me(request, required=True):
    me = getattr(request.user, 'nikah_profile', None)
    if me is None and required:
        raise ApiError(_('Сначала заполните анкету — это займёт около 5 минут.'), 409, 'no_profile')
    if me is not None:
        deck.touch(me)
    return me


def _labels(options, gender):
    """[(ключ, подпись брата, подпись сестры)] → [{key, name}] для нужного пола."""
    out = []
    for o in options:
        if len(o) == 3:
            key, m, f = o
            name = m if gender == 'M' else (f or '')
            if not name:
                continue
        else:
            key, name = o
        out.append({'key': key, 'name': str(name)})
    return out


def profile_json(p: NikahProfile, me: NikahProfile | None, full=False) -> dict:
    data = {
        'id': p.pk, 'name': p.display_name, 'age': p.age, 'gender': p.gender, 'place': p.place,
        'nationality': p.nationality, 'height': p.height, 'weight': p.weight,
        'verified': p.verified, 'online': p.is_online, 'premium': p.is_premium, 'boosted': p.is_boosted,
        'has_photo': p.shares_photo,
        'marital': p.label('marital'), 'madhhab': p.label('madhhab'), 'aqida': p.label('aqida'),
        'prayer': p.label('prayer'), 'look': p.label('look'), 'ready_when': p.label('ready_when'),
        'about': p.about if full else p.about[:220],
    }
    if me is not None and p.pk != me.pk:
        compat, why = getattr(p, 'compat', None), getattr(p, 'why', None)
        if compat is None:
            compat, why = services.compatibility(me, p)
        data['compat'], data['why'] = compat, [str(w) for w in why]
    if full:
        data.update({
            'quran': p.label('quran'), 'where_allah': p.label('where_allah'),
            'wife_number': p.label('wife_number'), 'polygyny': p.label('polygyny'),
            'children_want': p.label('children_want'), 'children_accept': p.label('children_accept'),
            'relocation': p.label('relocation'), 'manhaj_text': p.manhaj_text,
            'partner_expectations': p.partner_expectations, 'age_from': p.age_from, 'age_to': p.age_to,
        })
    return data


def _badges(me):
    incoming = (NikahInterest.objects.filter(to_profile=me)
                .exclude(from_profile__in=me.interests_sent.values('to_profile')).count())
    matches = NikahMatch.objects.filter(Q(sister=me) | Q(brother=me)).exclude(stage=NikahMatch.CLOSED)
    return {'incoming': incoming, 'waiting': sum(1 for m in matches if services.turn(m) == m.side(me))}


@api(auth=True, module='nikah')
def state(request):
    """Моё состояние в никяхе: анкета, статус, лимит, премиум, счётчики."""
    me = _me(request, required=False)
    st = SiteSettings.get_solo()
    if me is None:
        return {'profile': None, 'balance': int(balance_of(request.user))}
    return {
        'profile': {**profile_json(me, None, full=True), 'status': me.status, 'active': me.is_active,
                    'premium_until': me.premium_until.isoformat() if me.is_premium else None,
                    'photo_mode': me.photo_mode, 'own_photo': me.has_photo},
        'published': me.is_published, 'left': deck.left_today(me), 'limit': st.nikah_daily_limit,
        'skipped': deck.skipped_count(me), 'badges': _badges(me), 'balance': int(balance_of(request.user)),
        'telegram': bool(request.user.telegram_id),
        'invite': abs_url(request, f'/nikah/?ref={me.pk}'),
    }


@api(auth=True, module='nikah')
def options(request):
    """Справочники анкеты и фильтров — на языке пользователя, с подписями по полу."""
    from apps.nikah.geo import CITIES, countries_for, country_name
    lang = (get_language() or 'ru')[:2]
    g = request.GET.get('gender', 'M') if request.GET.get('gender') in ('M', 'F') else 'M'
    return {
        'marital': [x for x in _labels(C.MARITAL, g)], 'wife_number': _labels(C.WIFE_NUMBER, g),
        'polygyny': _labels(C.POLYGYNY, g), 'madhhab': _labels(C.MADHHAB, g), 'aqida': _labels(C.AQIDA, g),
        'prayer': _labels(C.PRAYER, g), 'quran': _labels(C.QURAN, g), 'where_allah': _labels(C.WHERE_ALLAH, g),
        'children_want': _labels(C.CHILDREN_WANT, g), 'children_accept': _labels(C.CHILDREN_ACCEPT, g),
        'ready_when': _labels(C.READY, g), 'has_children': [{'key': 'no', 'name': _('Нет')}, {'key': 'yes', 'name': _('Есть')}],
        'look': _labels(C.LOOK_M if g == 'M' else C.LOOK_F, g), 'relocation': _labels(C.RELOCATION, g),
        'photo_mode': _labels(C.PHOTO_MODE, g),
        'faith': [{'key': k, 'question': str(q), 'yes': str(o[0]), 'no': str(o[1])} for k, q, o in C.FAITH_QUESTIONS],
        'pledges': [{'key': k, 'title': str(t), 'text': str(d)} for k, t, d in C.PLEDGES],
        'countries': countries_for(lang),   # форма принимает название на любом из языков
        'cities': {country_name(k, lang): v for k, v in CITIES.items()},
        'nation_groups': [{'key': k, 'name': str(label)} for k, label, _w in deck.NATION_GROUPS],
        'ranges': deck.RANGES,
    }


# ---------- анкета ----------

TEXT_FIELDS = ('name', 'manhaj_text', 'about', 'partner_expectations')


@api(methods=('POST',), auth=True, module='nikah')
def profile_save(request):
    """Создать или изменить анкету. multipart (с фото) или JSON. Ошибки — по полям."""
    from apps.core.uploads import clean_image
    from apps.nikah.bot import send_for_moderation

    instance = getattr(request.user, 'nikah_profile', None)
    editing = instance is not None
    data = request.data
    form = NikahProfileForm(data, instance=instance, editing=editing)
    errors = {}
    faith = {k: str(data.get(f'faith_{k}', '')) for k, _q, _o in C.FAITH_QUESTIONS}
    faith_given = all(v in ('yes', 'no') for v in faith.values())
    if not editing and not faith_given:
        errors['faith'] = _('Ответьте на все вопросы.')
    if not editing and not all(str(data.get(f'agree_{k}', '')) in ('1', 'true', 'True') for k, _t, _d in C.PLEDGES):
        errors['pledges'] = _('Примите все пункты, чтобы завершить регистрацию.')
    photo = None
    try:
        photo = clean_image(request.FILES.get('photo'))
    except ValidationError as exc:
        errors['photo'] = exc.messages[0] if exc.messages else _('Загрузите фото в формате JPG или PNG.')
    has_photo = photo is not None or (editing and instance.has_photo)
    if data.get('photo_mode') == 'exchange' and not has_photo and 'photo' not in errors:
        errors['photo'] = _('Загрузите фото или выберите «Без фото».')
    before = {f: getattr(instance, f) for f in TEXT_FIELDS} if editing else {}
    if not form.is_valid() or errors:
        for name, errs in form.errors.items():
            errors.setdefault(name, str(errs[0]))
        from django.http import JsonResponse
        first = next(iter(errors.values()))
        return JsonResponse({'error': first, 'fields': errors}, status=400)
    profile = form.save(commit=False)
    profile.user = request.user
    if faith_given:
        profile.faith_answers = faith
    changed = True
    if editing:
        changed = photo is not None or any(getattr(profile, f) != before[f] for f in TEXT_FIELDS)
    else:
        profile.agreed_at = timezone.now()
        from django.core.cache import cache
        ref = cache.get(f'tgref:{request.user.telegram_id}') if request.user.telegram_id else None
        if ref:
            profile.referred_by = NikahProfile.objects.filter(pk=ref).exclude(user=request.user).first()
    if changed:
        profile.status = Moderation.PENDING       # тексты/фото — снова на проверку
    if photo is not None:
        services.store_photo(profile, photo)
    profile.save()
    log_action(request, 'Никях: анкета ' + ('изменена (приложение)' if editing else 'создана в приложении, обязательства приняты'),
               f'#{profile.pk}')
    if changed:
        send_for_moderation(profile)
    return {'ok': True, 'status': profile.status,
            'message': _('Анкета отправлена на проверку. Обычно это занимает до суток.') if changed else _('Сохранено.')}


@api(auth=True, module='nikah')
def profile_raw(request):
    """Моя анкета «как есть» (ключи вариантов) — для формы правки."""
    me = _me(request)
    return {f: getattr(me, f) for f in ('gender', 'name', 'age', 'age_from', 'age_to', 'country', 'city',
                                        'nationality', 'height', 'weight', 'marital', 'wife_number', 'polygyny',
                                        'madhhab', 'aqida', 'prayer', 'quran', 'where_allah', 'has_children',
                                        'children_want', 'children_accept', 'ready_when', 'look', 'relocation',
                                        'manhaj_text', 'about', 'partner_expectations', 'photo_mode')} | {
        'has_photo': me.has_photo}


@api(methods=('POST',), auth=True, module='nikah')
def pause(request):
    me = _me(request)
    me.is_active = not bool(request.data.get('pause'))
    me.save(update_fields=['is_active'])
    return {'ok': True, 'active': me.is_active}


# ---------- колода ----------

@api(auth=True, module='nikah')
def feed(request):
    """Колода: фильтры — в параметрах адреса (как в форме фильтра на сайте)."""
    me = _me(request)
    f = deck.clean_filters(request.GET)
    cards = deck.deck(me, f)
    saved = set(NikahSaved.objects.filter(user=request.user).values_list('profile_id', flat=True))
    st = SiteSettings.get_solo()
    return {'items': [{**profile_json(p, me), 'saved': p.pk in saved} for p in cards],
            'left': deck.left_today(me), 'limit': st.nikah_daily_limit, 'skipped': deck.skipped_count(me),
            'published': me.is_published, 'filters': f}


def _other(me, pk) -> NikahProfile:
    from apps.accounts.models import UserBlock
    p = get_object_or_404(NikahProfile, pk=pk)
    if p.pk != me.pk and (p.gender == me.gender or not p.is_published or UserBlock.between(me.user, p.user)):
        raise Http404
    return p


@api(auth=True, module='nikah')
def profile_detail(request, pk):
    me = _me(request)
    p = _other(me, pk)
    match = NikahMatch.objects.filter(Q(sister=me, brother=p) | Q(sister=p, brother=me)).first()
    return {**profile_json(p, me, full=True),
            'liked': NikahInterest.objects.filter(from_profile=me, to_profile=p).exists(),
            'likes_me': NikahInterest.objects.filter(from_profile=p, to_profile=me).exists(),
            'saved': NikahSaved.objects.filter(user=request.user, profile=p).exists(),
            'match_id': match.pk if match else None, 'user_id': p.user_id}


@api(methods=('POST',), auth=True, module='nikah')
def skip(request, pk):
    me = _me(request)
    p = _other(me, pk)
    if deck.left_today(me) == 0:
        raise ApiError(_('Анкеты на сегодня закончились'), 429, 'limit')
    deck.skip(me, p)
    return {'ok': True, 'left': deck.left_today(me)}


@api(methods=('POST',), auth=True, module='nikah')
def interest(request, pk):
    me = _me(request)
    p = get_object_or_404(NikahProfile, pk=pk, status=Moderation.APPROVED, is_active=True)
    _other(me, pk)
    if not me.is_published:
        raise ApiError(_('Интерес можно проявлять, когда вашу анкету одобрит модератор.'), 403, 'not_published')
    if request.data.get('undo'):
        if not NikahMatch.objects.filter(Q(sister=me, brother=p) | Q(sister=p, brother=me)).exists():
            services.withdraw_interest(me, p)
        return {'ok': True}
    if request.data.get('from_deck') and deck.left_today(me) == 0:
        raise ApiError(_('Анкеты на сегодня закончились'), 429, 'limit')
    try:
        match = services.send_interest(me, p)
    except ValueError as exc:
        raise ApiError(str(exc)) from exc
    return {'ok': True, 'left': deck.left_today(me), 'match_id': match.pk if match else None}


@api(methods=('POST',), auth=True, module='nikah')
def save_toggle(request, pk):
    me = _me(request)
    p = _other(me, pk)
    obj, created = NikahSaved.objects.get_or_create(user=request.user, profile=p)
    if not created:
        obj.delete()
    return {'ok': True, 'saved': created}


@api(methods=('POST',), auth=True, module='nikah')
def restore(request):
    me = _me(request)
    try:
        n = deck.restore_skipped(me, request.user)
    except InsufficientFunds:
        raise ApiError(NO_MONEY, 402, 'money') from None
    return {'ok': True, 'restored': n}


@api(methods=('POST',), auth=True, module='nikah')
def premium(request):
    me = _me(request)
    try:
        deck.buy_premium(me, request.user)
    except InsufficientFunds:
        raise ApiError(NO_MONEY, 402, 'money') from None
    except ValueError as exc:
        raise ApiError(str(exc)) from exc
    me.refresh_from_db()
    return {'ok': True, 'premium_until': me.premium_until.isoformat()}


@api(auth=True, module='nikah')
def lists(request):
    """Интересы: входящие, отправленные, пары; и сохранённые."""
    from apps.accounts.models import UserBlock
    me = _me(request)
    blocked = UserBlock.ids_for(request.user)
    sent_ids = set(me.interests_sent.values_list('to_profile_id', flat=True))
    incoming = [i.from_profile for i in NikahInterest.objects.filter(to_profile=me).select_related('from_profile')
                if i.from_profile_id not in sent_ids and i.from_profile.is_published
                and i.from_profile.user_id not in blocked]
    sent = [i.to_profile for i in me.interests_sent.select_related('to_profile')
            if not NikahInterest.objects.filter(from_profile=i.to_profile, to_profile=me).exists()]
    matches = [services.refresh(m) for m in NikahMatch.objects.filter(Q(sister=me) | Q(brother=me))
               .select_related('sister', 'brother')]
    saved = [s.profile for s in NikahSaved.objects.filter(user=request.user).select_related('profile')
             if s.profile.is_published and s.profile.gender != me.gender]
    return {
        'incoming': [profile_json(p, me) for p in incoming],
        'sent': [profile_json(p, me) for p in sent],
        'saved': [profile_json(p, me) for p in saved],
        'matches': [{'id': m.pk, 'stage': m.stage, 'stage_name': str(m.get_stage_display()),
                     'my_turn': services.turn(m) == m.side(me), 'thread_id': m.thread_id,
                     'partner': profile_json(m.other(me), me)} for m in matches],
    }


# ---------- пара: обмен фото → решение → чат ----------

def _match(request, pk):
    me = _me(request)
    m = get_object_or_404(NikahMatch.objects.select_related('sister', 'brother'), pk=pk)
    if me.pk not in (m.sister_id, m.brother_id):
        raise Http404
    return me, services.refresh(m)


def match_json(request, me, m) -> dict:
    side = m.side(me)
    other_side = 'brother' if side == 'sister' else 'sister'
    return {
        'id': m.pk, 'stage': m.stage, 'stage_name': str(m.get_stage_display()), 'side': side,
        'turn': services.turn(m), 'opened': bool(getattr(m, f'{side}_viewed_at')),
        'my_ok': getattr(m, f'{side}_ok'), 'their_ok': getattr(m, f'{other_side}_ok'),
        'seconds': services.seconds_left(m, side), 'minutes': services.photo_minutes(),
        'price': services.chat_price(), 'chat_paid': m.chat_paid, 'thread_id': m.thread_id,
        'partner': profile_json(m.other(me), me, full=True),
        'balance': int(balance_of(request.user)) if side == 'brother' else None,
    }


@api(auth=True, module='nikah')
def match(request, pk):
    me, m = _match(request, pk)
    return match_json(request, me, m)


@api(methods=('POST',), auth=True, module='nikah')
def match_open(request, pk):
    me, m = _match(request, pk)
    if not request.data.get('oath'):
        raise ApiError(_('Подтвердите обещание не сохранять и не пересылать фото.'))
    try:
        services.open_photo(m, m.side(me))
    except ValueError as exc:
        raise ApiError(str(exc)) from exc
    log_action(request, 'Никях: открыто фото в приложении (обещание принято)', f'пара #{m.pk}')
    m.refresh_from_db()
    return match_json(request, me, services.refresh(m))


@api(auth=True, module='nikah')
def match_photo(request, pk):
    me, m = _match(request, pk)
    side = m.side(me)
    if services.turn(m) != side or not getattr(m, f'{side}_viewed_at') or services.seconds_left(m, side) <= 0:
        raise ApiError(_('Нет доступа'), 403, 'forbidden')
    partner = m.other(me)
    if not partner.has_photo:
        raise Http404
    resp = HttpResponse(services.watermarked_photo(partner, request.user), content_type='image/jpeg')
    resp['Cache-Control'] = 'no-store, private'
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp


@api(methods=('POST',), auth=True, module='nikah')
def match_decide(request, pk):
    me, m = _match(request, pk)
    try:
        services.decide(m, m.side(me), bool(request.data.get('ok')))
    except ValueError as exc:
        raise ApiError(str(exc)) from exc
    m.refresh_from_db()
    return match_json(request, me, services.refresh(m))


@api(methods=('POST',), auth=True, module='nikah')
def match_pay(request, pk):
    me, m = _match(request, pk)
    try:
        services.pay_chat(m, request.user)
    except InsufficientFunds:
        raise ApiError(NO_MONEY, 402, 'money') from None
    except ValueError as exc:
        raise ApiError(str(exc)) from exc
    m.refresh_from_db()
    return match_json(request, me, services.refresh(m))
