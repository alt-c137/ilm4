"""Никях: знакомство, лента без фото, интерес → взаимность → обмен фото → чат.

Страницы: /nikah/ (о сервисе или лента), анкета (мастер 15 шагов), интересы,
сохранённые, чаты, «Я», пара (обмен фото). Работает и на сайте, и внутри Telegram
(мини-приложение: вход по подписи Telegram — apps/accounts/telegram.py).
"""
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts import phone_verify
from apps.accounts.audit import log_action
from apps.core.decorators import module_required
from apps.core.models import Moderation, SiteSettings
from apps.core.uploads import clean_image
from apps.wallet import services as wallet
from apps.wallet.models import Transaction
from apps.wallet.services import InsufficientFunds

from . import choices as C
from . import deck, services
from .forms import NikahProfileForm
from .models import NikahInterest, NikahMatch, NikahProfile, NikahSaved

FEED_LIMIT = 60


def _me(request):
    return getattr(request.user, 'nikah_profile', None) if request.user.is_authenticated else None


def profile_required(view):
    """Раздел для участников с анкетой: без анкеты — на мастер."""
    @wraps(view)
    @login_required
    @module_required('nikah')
    def wrapped(request, *args, **kwargs):
        if phone_verify.needed(request.user, 'nikah'):      # один номер — одна анкета
            return phone_verify.redirect_to_verify(request, 'nikah')
        me = _me(request)
        if me is None:
            messages.info(request, _('Сначала заполните анкету — это займёт около 5 минут.'))
            return redirect('nikah:create')
        request.nikah = me
        deck.touch(me)
        return view(request, *args, **kwargs)
    return wrapped


def _badges(me):
    """Счётчики для вкладок: новые интересы, пары, ждущие действия."""
    incoming = (NikahInterest.objects.filter(to_profile=me)
                .exclude(from_profile__in=me.interests_sent.values('to_profile')).count())
    matches = NikahMatch.objects.filter(Q(sister=me) | Q(brother=me)).exclude(stage=NikahMatch.CLOSED)
    waiting = sum(1 for m in matches if services.turn(m) == m.side(me))
    return {'incoming': incoming, 'waiting': waiting}


def _ctx(request, tab, **extra):
    from django.conf import settings

    me = getattr(request, 'nikah', None) or _me(request)
    st = SiteSettings.get_solo()
    return {'me': me, 'tab': tab, 'badges': _badges(me) if me else {},
            'tg_bot': getattr(settings, 'TELEGRAM_BOT_USERNAME', ''),
            'balance': wallet.balance_of(request.user) if me else None,
            'premium_on': st.nikah_premium_enabled, **extra}


# ---------- главная раздела: о сервисе (гость) или лента ----------

@module_required('nikah')
def home(request):
    ref = request.GET.get('ref', '')
    if ref.isdigit():
        request.session['nikah_ref'] = int(ref)
    me = _me(request)
    if me is None:
        return render(request, 'nikah/intro.html', _ctx(request, 'feed', minutes=services.photo_minutes()))
    if phone_verify.needed(request.user, 'nikah'):
        return phone_verify.redirect_to_verify(request, 'nikah')
    request.nikah = me
    return feed(request)


def feed(request):
    """Колода анкет: свайп вправо — интерес, влево — пропуск. Дневной лимит без премиума."""
    me = request.nikah
    deck.touch(me)
    f = request.session.get(deck.SESSION_KEY, {})
    cards = deck.deck(me, f)
    saved = set(NikahSaved.objects.filter(user=request.user).values_list('profile_id', flat=True))
    for p in cards:
        p.saved = p.pk in saved
    st = SiteSettings.get_solo()
    return render(request, 'nikah/feed.html', _ctx(
        request, 'feed', cards=cards, f=f, filtered=bool(f), left=deck.left_today(me),
        limit=st.nikah_daily_limit, skipped=deck.skipped_count(me), restore_price=st.nikah_restore_price,
        premium_price=st.nikah_premium_price, premium_days=st.nikah_premium_days,
        nation_groups=[(g, label) for g, label, _k in deck.NATION_GROUPS], geo=_geo(),

        other_gender='F' if me.gender == 'M' else 'M',
        opts={'madhhab': C.MADHHAB, 'aqida': C.AQIDA, 'prayer': C.PRAYER, 'ready_when': C.READY,
              'marital': [m for m in C.MARITAL if not (me.gender == 'M' and m[0] == 'married')],
              'look': C.LOOK_F if me.gender == 'M' else C.LOOK_M, 'children_want': C.CHILDREN_WANT,
              'relocation': C.RELOCATION}))


def _wants_json(request):
    return 'application/json' in request.headers.get('Accept', '')


@profile_required
@require_POST
def skip(request, pk):
    me = request.nikah
    p = get_object_or_404(NikahProfile, pk=pk)
    left = deck.left_today(me)
    if left == 0:
        return JsonResponse({'ok': False, 'limit': True}, status=429) if _wants_json(request) \
            else redirect('nikah:home')
    deck.skip(me, p)
    if _wants_json(request):
        return JsonResponse({'ok': True, 'left': deck.left_today(me)})
    return redirect('nikah:home')


@profile_required
@require_POST
def filters(request):
    if request.POST.get('reset') == '1':
        request.session.pop(deck.SESSION_KEY, None)
    else:
        request.session[deck.SESSION_KEY] = deck.clean_filters(request.POST)
    return redirect('nikah:home')


@profile_required
@require_POST
def restore(request):
    try:
        n = deck.restore_skipped(request.nikah, request.user)
    except InsufficientFunds:
        messages.error(request, _('На балансе не хватает средств — пополните кошелёк.'))
        return redirect('wallet:index')
    messages.success(request, _('Вернули в ленту: {n}.').format(n=n) if n else _('Отклонённых анкет нет.'))
    return redirect('nikah:home')


@profile_required
def premium(request):
    me = request.nikah
    st = SiteSettings.get_solo()
    if request.method == 'POST':
        try:
            deck.buy_premium(me, request.user)
        except InsufficientFunds:
            messages.error(request, _('На балансе не хватает средств — пополните кошелёк.'))
            return redirect('wallet:index')
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect('nikah:premium')
        messages.success(request, _('Премиум подключён. БаракаЛлаху фик!'))
        return redirect('nikah:premium')
    return render(request, 'nikah/premium.html', _ctx(
        request, 'me', price=st.nikah_premium_price, days=st.nikah_premium_days, limit=st.nikah_daily_limit,
        restore_price=st.nikah_restore_price))


@login_required
@module_required('nikah')
def detail(request, pk):
    """Анкета. Модератор видит любую (на проверке, того же пола) — с кнопками «Одобрить / Отклонить»."""
    from apps.core import moderation
    if moderation.can_moderate(request.user, NikahProfile):
        p = get_object_or_404(NikahProfile, pk=pk)
        me = _me(request)
        if me is None or (p.pk != me.pk and (p.gender == me.gender or not p.is_published)):
            p.compat, p.why = None, []
            return render(request, 'nikah/detail.html', _ctx(request, 'feed', p=p, moderating=True))
    return _detail(request, pk)


@profile_required
def _detail(request, pk):
    me = request.nikah
    p = get_object_or_404(NikahProfile, pk=pk)
    from apps.accounts.models import UserBlock
    if p.pk != me.pk and (p.gender == me.gender or not p.is_published or UserBlock.between(me.user, p.user)):
        raise Http404
    p.compat, p.why = services.compatibility(me, p) if p.pk != me.pk else (None, [])
    match = NikahMatch.objects.filter(Q(sister=me, brother=p) | Q(sister=p, brother=me)).first()
    return render(request, 'nikah/detail.html', _ctx(
        request, 'feed', p=p, match=match,
        liked=NikahInterest.objects.filter(from_profile=me, to_profile=p).exists(),
        likes_me=NikahInterest.objects.filter(from_profile=p, to_profile=me).exists(),
        saved=NikahSaved.objects.filter(user=request.user, profile=p).exists()))


@profile_required
@require_POST
def interest(request, pk):
    me = request.nikah
    p = get_object_or_404(NikahProfile, pk=pk, status=Moderation.APPROVED, is_active=True)
    if not me.is_published:
        text = _('Интерес можно проявлять, когда вашу анкету одобрит модератор.')
        if _wants_json(request):
            return JsonResponse({'ok': False, 'error': text}, status=403)
        messages.info(request, text)
        return redirect('nikah:detail', pk=pk)
    back = request.POST.get('back', '')
    if request.POST.get('from_deck') == '1' and deck.left_today(me) == 0:
        return JsonResponse({'ok': False, 'limit': True}, status=429) if _wants_json(request) \
            else redirect('nikah:home')
    if request.POST.get('undo') == '1':
        if not NikahMatch.objects.filter(Q(sister=me, brother=p) | Q(sister=p, brother=me)).exists():
            services.withdraw_interest(me, p)
        return redirect(back if back.startswith('/nikah/') else 'nikah:home')
    try:
        match = services.send_interest(me, p)
    except ValueError as exc:
        if _wants_json(request):
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        messages.error(request, str(exc))
        return redirect('nikah:home')
    if _wants_json(request):
        return JsonResponse({'ok': True, 'left': deck.left_today(me),
                             'match': reverse('nikah:match', args=[match.pk]) if match else ''})
    if match:
        messages.success(request, _('Взаимная симпатия! Посмотрите, что дальше.'))
        return redirect('nikah:match', pk=match.pk)
    messages.success(request, _('Интерес отправлен. Если он взаимный — вы оба узнаете.'))
    return redirect(back if back.startswith('/nikah/') else 'nikah:home')


@profile_required
@require_POST
def save_toggle(request, pk):
    p = get_object_or_404(NikahProfile, pk=pk)
    obj, created = NikahSaved.objects.get_or_create(user=request.user, profile=p)
    if not created:
        obj.delete()
    back = request.POST.get('back', '')
    return redirect(back if back.startswith('/nikah/') else 'nikah:saved')


@profile_required
def interests(request):
    me = request.nikah
    from apps.accounts.models import UserBlock
    blocked = UserBlock.ids_for(request.user)
    sent_ids = set(me.interests_sent.values_list('to_profile_id', flat=True))
    incoming = [i.from_profile for i in NikahInterest.objects.filter(to_profile=me).select_related('from_profile')
                if i.from_profile_id not in sent_ids and i.from_profile.is_published
                and i.from_profile.user_id not in blocked]
    sent = [i.to_profile for i in me.interests_sent.select_related('to_profile')
            if not NikahInterest.objects.filter(from_profile=i.to_profile, to_profile=me).exists()]
    matches = [services.refresh(m) for m in NikahMatch.objects.filter(Q(sister=me) | Q(brother=me))
               .select_related('sister', 'brother')]
    for m in matches:
        m.partner, m.my_turn = m.other(me), services.turn(m) == m.side(me)
    for p in incoming + sent:
        p.compat, p.why = services.compatibility(me, p)
    return render(request, 'nikah/interests.html', _ctx(
        request, 'interests', incoming=incoming, sent=sent, matches=matches,
        show=request.GET.get('show', 'incoming')))


@profile_required
def saved(request):
    me = request.nikah
    profiles = [s.profile for s in NikahSaved.objects.filter(user=request.user).select_related('profile')
                if s.profile.is_published and s.profile.gender != me.gender]
    for p in profiles:
        p.compat, p.why = services.compatibility(me, p)
        p.saved = True
    return render(request, 'nikah/saved.html', _ctx(request, 'saved', profiles=profiles))


@profile_required
def chats(request):
    me = request.nikah
    matches = list(NikahMatch.objects.filter(Q(sister=me) | Q(brother=me), stage=NikahMatch.CHAT)
                   .select_related('sister', 'brother', 'thread'))
    for m in matches:
        m.partner = m.other(me)
    return render(request, 'nikah/chats.html', _ctx(request, 'chats', matches=matches,
                                                    price=services.chat_price()))


# ---------- пара: обмен фото и открытие чата ----------

def _my_match(request, pk):
    me = request.nikah
    m = get_object_or_404(NikahMatch.objects.select_related('sister', 'brother'), pk=pk)
    if me.pk not in (m.sister_id, m.brother_id):
        raise Http404
    return me, services.refresh(m)


@profile_required
def match(request, pk):
    me, m = _my_match(request, pk)
    side = m.side(me)
    other_side = 'brother' if side == 'sister' else 'sister'
    return render(request, 'nikah/match.html', _ctx(
        request, 'interests', m=m, partner=m.other(me), side=side, turn=services.turn(m),
        opened=getattr(m, f'{side}_viewed_at'), my_ok=getattr(m, f'{side}_ok'),
        their_ok=getattr(m, f'{other_side}_ok'), seconds=services.seconds_left(m, side),
        minutes=services.photo_minutes(), price=services.chat_price(), tg_photo=services.tg_ready(request.user),
        balance=wallet.balance_of(request.user) if side == 'brother' else None))


@profile_required
@require_POST
def match_open(request, pk):
    me, m = _my_match(request, pk)
    if request.POST.get('oath') != '1':
        messages.error(request, _('Подтвердите обещание не сохранять и не пересылать фото.'))
        return redirect('nikah:match', pk=pk)
    try:
        services.open_photo(m, m.side(me))
        log_action(request, 'Никях: открыто фото (обещание принято)', f'пара #{m.pk}')
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('nikah:match', pk=pk)
    if request.POST.get('via') == 'tg':
        m.refresh_from_db()
        if services.send_photo_to_telegram(m, m.side(me), request.user):
            messages.success(request, _('Фото отправлено в Telegram — откройте чат с ботом. Решение примите здесь.'))
        else:
            messages.error(request, _('Не удалось отправить в Telegram — фото открыто здесь.'))
    return redirect('nikah:match', pk=pk)


@profile_required
def match_photo(request, pk):
    """Фото собеседника: только в свою очередь, после «открыть», пока идёт таймер."""
    me, m = _my_match(request, pk)
    side = m.side(me)
    if services.turn(m) != side or not getattr(m, f'{side}_viewed_at') or services.seconds_left(m, side) <= 0:
        raise PermissionDenied
    partner = m.other(me)
    if not partner.has_photo:
        raise Http404
    resp = HttpResponse(services.watermarked_photo(partner, request.user), content_type='image/jpeg')
    resp['Cache-Control'] = 'no-store, private'
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp


@profile_required
@require_POST
def match_decide(request, pk):
    me, m = _my_match(request, pk)
    try:
        services.decide(m, m.side(me), request.POST.get('ok') == '1')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('nikah:match', pk=pk)


@profile_required
@require_POST
def match_pay(request, pk):
    m = _my_match(request, pk)[1]
    try:
        services.pay_chat(m, request.user)
    except InsufficientFunds:
        messages.error(request, _('На балансе не хватает средств — пополните кошелёк.'))
        return redirect('wallet:index')
    except ValueError as exc:
        messages.error(request, str(exc))
    m.refresh_from_db()
    return redirect('chat:thread', pk=m.thread_id) if m.thread_id else redirect('nikah:match', pk=pk)


# ---------- «Я» и анкета ----------

@profile_required
def mine(request):
    me = request.nikah
    return render(request, 'nikah/mine.html', _ctx(
        request, 'me', p=me, balance=wallet.balance_of(request.user),
        boost_price=SiteSettings.get_solo().nikah_boost_price))


@login_required
@module_required('nikah')
@phone_verify.required('nikah')
def create(request):
    if _me(request):
        return redirect('nikah:edit')
    return _wizard(request, None)


TEXT_FIELDS = ('name', 'manhaj_text', 'about', 'partner_expectations')


@profile_required
def edit(request):
    """Редактирование одной страницей (все пункты анкеты сразу). Тексты или фото
    поменялись — анкета снова уходит на проверку; остальное меняется сразу."""
    me = request.nikah
    before = {f: getattr(me, f) for f in TEXT_FIELDS}
    form = NikahProfileForm(request.POST or None, instance=me, editing=True)
    photo_error = ''
    if request.method == 'POST':
        photo = None
        try:
            photo = clean_image(request.FILES.get('photo'))
        except ValidationError as exc:
            photo_error = exc.messages[0] if exc.messages else _('Загрузите фото JPG или PNG.')
        if request.POST.get('photo_mode') == 'exchange' and not (photo or me.has_photo) and not photo_error:
            photo_error = _('Загрузите фото или выберите «Без фото».')
        if form.is_valid() and not photo_error:
            profile = form.save(commit=False)
            texts_changed = any(getattr(profile, f) != before[f] for f in TEXT_FIELDS)
            if photo is not None:
                services.store_photo(profile, photo)
            if texts_changed or photo is not None:
                profile.status = Moderation.PENDING
            profile.save()
            log_action(request, 'Никях: анкета изменена', f'#{profile.pk}')
            if profile.status == Moderation.PENDING and (texts_changed or photo is not None):
                from .bot import send_for_moderation
                send_for_moderation(profile)
                messages.success(request, _('Сохранено. Тексты и фото проверит модератор — обычно до суток.'))
            else:
                messages.success(request, _('Сохранено.'))
            return redirect('nikah:mine')
    return render(request, 'nikah/edit.html', _ctx(
        request, 'me', form=form, photo_error=photo_error, p=me, opts=_opts(), geo=_geo(),
        ages=range(18, 81), heights=range(120, 231), weights=range(40, 201)))


def _opts():
    return {
        'marital': C.MARITAL, 'wife_number': C.WIFE_NUMBER, 'polygyny': C.POLYGYNY,
        'madhhab': C.MADHHAB, 'aqida': C.AQIDA, 'prayer': C.PRAYER, 'quran': C.QURAN,
        'where_allah': C.WHERE_ALLAH, 'children_want': C.CHILDREN_WANT, 'children_accept': C.CHILDREN_ACCEPT,
        'ready_when': C.READY, 'has_children': [('no', _('Нет')), ('yes', _('Есть'))],
        'look_m': C.LOOK_M, 'look_f': C.LOOK_F, 'relocation': C.RELOCATION, 'photo_mode': C.PHOTO_MODE,
    }


def _geo():
    """Страны и города для выбора — на языке интерфейса (в базе хранится русское название)."""
    from django.utils.translation import get_language

    from .geo import CITIES, countries_for, country_name
    lang = (get_language() or 'ru')[:2]
    return {'countries': countries_for(lang), 'cities': {country_name(k, lang): v for k, v in CITIES.items()}}


@profile_required
def settings_page(request):
    """Настройки: режим фото, верификация, уведомления, лайки сегодня, платежи, приглашение друзей."""
    me = request.nikah
    if request.method == 'POST' and request.POST.get('photo_mode') in ('exchange', 'none'):
        mode = request.POST['photo_mode']
        if mode == 'exchange' and not me.has_photo:
            messages.info(request, _('Сначала добавьте фото в анкете.'))
            return redirect(reverse('nikah:edit') + '#photo')
        me.photo_mode = mode
        me.save(update_fields=['photo_mode'])
        messages.success(request, _('Сохранено.'))
        return redirect('nikah:settings')
    from django.conf import settings as dj
    bot = getattr(dj, 'TELEGRAM_BOT_USERNAME', '')
    site = getattr(dj, 'SITE_URL', '').rstrip('/') or request.build_absolute_uri('/').rstrip('/')
    st = SiteSettings.get_solo()
    return render(request, 'nikah/settings.html', _ctx(
        request, 'me', p=me, left=deck.left_today(me), limit=st.nikah_daily_limit,
        invite_web=f'{site}/nikah/?ref={me.pk}', invite_tg=f'https://t.me/{bot}?start=ref_{me.pk}' if bot else '',
        invited=me.invited.count(), bonus_days=st.nikah_ref_bonus_days,
        verify_tg=f'https://t.me/{bot}?start=verify' if bot else ''))


@profile_required
@require_POST
def verify(request):
    """Верификация кружком: бот присылает инструкцию в Telegram."""
    from .bot import send_verify_instructions
    if request.user.telegram_id and send_verify_instructions(request.user.telegram_id):
        messages.success(request, _('Инструкция отправлена в Telegram — запишите видео-кружок боту.'))
    else:
        messages.info(request, _('Верификация проходит в Telegram: откройте бота по кнопке ниже.'))
    return redirect('nikah:settings')


def _wizard(request, instance):
    editing = instance is not None
    form = NikahProfileForm(request.POST or None, instance=instance, editing=editing)
    step, step_errors = 1, {}
    if request.method == 'POST':
        faith = {k: request.POST.get(f'faith_{k}', '') for k, _q, _o in C.FAITH_QUESTIONS}
        faith_given = all(v in ('yes', 'no') for v in faith.values())
        if not editing and not faith_given:
            step_errors[14] = _('Ответьте на все вопросы.')
        if not editing and not all(request.POST.get(f'agree_{k}') == '1' for k, _t, _d in C.PLEDGES):
            step_errors[15] = _('Примите все пункты, чтобы завершить регистрацию.')
        photo = None
        try:
            photo = clean_image(request.FILES.get('photo'))
        except ValidationError as exc:
            step_errors[13] = exc.messages[0] if exc.messages else _('Загрузите фото в формате JPG или PNG.')
        has_photo = photo is not None or (editing and instance.has_photo)
        if request.POST.get('photo_mode') == 'exchange' and not has_photo and 13 not in step_errors:
            step_errors[13] = _('Загрузите фото или выберите «Без фото».')
        if form.is_valid() and not step_errors:
            profile = form.save(commit=False)
            profile.user = request.user
            if faith_given:
                profile.faith_answers = faith
            if not editing:
                profile.agreed_at = timezone.now()
                ref = request.session.pop('nikah_ref', None)
                if not ref and request.user.telegram_id:
                    from django.core.cache import cache
                    ref = cache.get(f'tgref:{request.user.telegram_id}')
                if ref:
                    profile.referred_by = NikahProfile.objects.filter(pk=ref).exclude(user=request.user).first()
            profile.status = Moderation.PENDING       # любая правка — снова на проверку
            if photo is not None:
                services.store_photo(profile, photo)
            profile.save()
            log_action(request, 'Никях: анкета ' + ('изменена' if editing else 'создана, обязательства приняты'),
                       f'#{profile.pk}')
            from .bot import send_for_moderation
            send_for_moderation(profile)
            messages.success(request, _('Анкета отправлена на проверку. Обычно это занимает до суток.'))
            return redirect('nikah:mine')
        step = min([form.first_error_step() if form.errors else 99, *step_errors.keys()])
    # первая ошибка каждого шага — для вывода под вопросами
    from .forms import STEP_OF
    errs = dict(step_errors)
    for name, errors in form.errors.items():
        errs.setdefault(STEP_OF.get(name, 1), errors[0])
    return render(request, 'nikah/wizard.html', _ctx(
        request, 'me', form=form, editing=editing, step=step, errs=errs,
        gender=(instance.gender if editing else request.POST.get('gender', '')),
        faith_q=C.FAITH_QUESTIONS, pledges=C.PLEDGES, has_photo=editing and instance.has_photo,
        opts={
            'marital': C.MARITAL, 'wife_number': C.WIFE_NUMBER, 'polygyny': C.POLYGYNY,
            'madhhab': C.MADHHAB, 'aqida': C.AQIDA, 'prayer': C.PRAYER, 'quran': C.QURAN,
            'where_allah': C.WHERE_ALLAH, 'children_want': C.CHILDREN_WANT,
            'children_accept': C.CHILDREN_ACCEPT, 'ready_when': C.READY,
            'has_children': [('no', _('Нет')), ('yes', _('Есть'))],
            'look_m': C.LOOK_M, 'look_f': C.LOOK_F, 'relocation': C.RELOCATION, 'photo_mode': C.PHOTO_MODE,
        },
        faith_cur={k: request.POST.get(f'faith_{k}') or (instance.faith_answers.get(k) if editing else '')
                   for k, _q, _o in C.FAITH_QUESTIONS},
        countries=C.COUNTRIES, geo=_geo(),
    ))


@module_required('nikah')
def how(request):
    return render(request, 'nikah/how.html', _ctx(request, 'me', minutes=services.photo_minutes()))


@login_required
@module_required('nikah')
@require_POST
def boost(request):
    """Поднять свою анкету в ленте на 7 дней — платно."""
    profile = _me(request)
    if not profile:
        return redirect('nikah:create')
    price = SiteSettings.get_solo().nikah_boost_price
    try:
        wallet.debit(request.user, price, Transaction.PURCHASE, ref='nikah:boost', note='Буст анкеты никаха')
    except InsufficientFunds:
        messages.error(request, _('Недостаточно средств — пополните кошелёк.'))
        return redirect('wallet:index')
    base = profile.boosted_until if profile.is_boosted else timezone.now()
    profile.boosted_until = base + timedelta(days=7)
    profile.save(update_fields=['boosted_until'])
    messages.success(request, _('Анкета поднята на 7 дней.'))
    return redirect('nikah:mine')


@login_required
@require_POST
def pause(request):
    """Скрыть / вернуть свою анкету в ленту."""
    profile = _me(request)
    if profile:
        profile.is_active = not profile.is_active
        profile.save(update_fields=['is_active'])
        messages.success(request, _('Анкета снова в ленте.') if profile.is_active else _('Анкета скрыта из ленты.'))
    return redirect('nikah:mine')


@login_required
def admin_photo(request, pk):
    """Фото анкеты для модератора (с водяным знаком модератора, запись в журнал)."""
    if not request.user.is_staff:
        raise PermissionDenied
    p = get_object_or_404(NikahProfile, pk=pk)
    if not p.has_photo:
        raise Http404
    log_action(request, 'Никях: модератор открыл фото анкеты', f'#{p.pk}')
    resp = HttpResponse(services.watermarked_photo(p, request.user), content_type='image/jpeg')
    resp['Cache-Control'] = 'no-store, private'
    return resp


@profile_required
@require_POST
def witness_invite(request):
    """Создать ссылку-приглашение для свидетеля (или убрать свидетеля)."""
    import secrets
    me = request.nikah
    if request.POST.get('remove') == '1':
        services.remove_witness(me)
        messages.success(request, _('Свидетель убран из ваших чатов.'))
    else:
        me.witness_token = secrets.token_urlsafe(16)[:24]
        me.save(update_fields=['witness_token'])
        messages.success(request, _('Ссылка готова — отправьте её махраму. Она одноразовая.'))
    return redirect(reverse('nikah:settings') + '#witness')


@login_required
@module_required('nikah')
def witness_join(request, token):
    """Махрам открыл ссылку: подтверждает, что становится свидетелем."""
    p = NikahProfile.objects.filter(witness_token=token).exclude(witness_token='').first()
    if p is None:
        messages.error(request, _('Ссылка недействительна или уже использована.'))
        return redirect('nikah:home')
    if p.user_id == request.user.pk:
        messages.info(request, _('Это ваша ссылка — отправьте её махраму.'))
        return redirect('nikah:settings')
    if request.method == 'POST':
        services.set_witness(p, request.user)
        log_action(request, 'Никях: стал свидетелем', f'анкета #{p.pk}')
        messages.success(request, _('Вы свидетель в чатах никяха: {v1}. Чаты — в разделе «Чаты» сайта.').format(v1=p.display_name))
        return redirect('chat:inbox')
    return render(request, 'nikah/witness_join.html', _ctx(request, 'me', p=p))
