"""«Витрина» — вид главной, где сервисы не спрятаны в меню, а показаны живыми плитками: что в каждом есть прямо сейчас.

Зачем: мессенджер и лента не должны заслонять остальное — объявления, работу, услуги, попутчиков, карту, форум.
Каждая плитка = раздел: его цвет, свежие записи (или личное: «новых сообщений: 3», «2 из 5 дел»), главная кнопка.
Человек сам решает, какие плитки видеть и в каком порядке (User.ui['widgets'], ['widgets_off']); сайт и приложение
берут плитки отсюда — widgets(user). Новый раздел получает плитку автоматически: описание берётся из каталога.
"""
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from .catalog import DESCR, GROUPS
from .models import Moderation, ModuleConfig

# цвет раздела — по нему раздел узнаётся с первого взгляда (плитка, значок, кнопка)
COLORS = {
    'chat': '#3b82f6', 'feed': '#8b5cf6', 'communities': '#6366f1', 'stories': '#ec4899', 'assistant': '#7c3aed',
    'prayer': '#0d9488', 'tracker': '#10b981', 'library': '#a16207', 'forum': '#14b8a6', 'news': '#64748b',
    'buy': '#f59e0b', 'services': '#d946ef', 'jobs': '#2563eb', 'transport': '#ef4444', 'migration': '#0ea5e9',
    'map': '#22c55e', 'health': '#f43f5e', 'nikah': '#e0457b', 'refugee': '#f97316', 'wallet': '#16a34a',
}
DEFAULT_COLOR = '#6d5efc'
# раздел → виды публикаций реестра (apps/core/publications.py), из которых берутся свежие записи
PUBS = {'buy': ['buy'], 'jobs': ['jobs'], 'services': ['services'], 'transport': ['trips', 'transport'], 'map': ['places'],
        'health': ['doctors'], 'migration': ['stories'], 'library': ['books'], 'forum': ['topics']}
# главная кнопка плитки: (подпись, адрес)
ACTIONS = {
    'buy': (_lazy('Подать'), '/buy/add/'), 'jobs': (_lazy('Разместить'), '/jobs/add/'), 'services': (_lazy('Предложить'), '/services/add/'),
    'transport': (_lazy('Поездка'), '/transport/trips/add/'), 'map': (_lazy('Добавить'), '/map/add/'), 'forum': (_lazy('Спросить'), '/forum/ask/'),
    'chat': (_lazy('Написать'), '/chat/contacts/'), 'feed': (_lazy('Запись'), '/feed/'), 'communities': (_lazy('Создать'), '/communities/new/'),
    'health': (_lazy('Добавить'), '/health/add/'), 'migration': (_lazy('Рассказать'), '/migration/add/'),
}
ROWS = 3
SKIP = {'wallet', 'shorts', 'gifts'}
# порядок по умолчанию: общение и намаз, сразу за ними — сервисы (чтобы они не терялись за мессенджером), дальше остальное
FIRST = ['chat', 'prayer', 'buy', 'jobs', 'services', 'transport', 'map', 'communities', 'feed', 'health', 'nikah', 'tracker',
         'forum', 'news', 'migration', 'refugee', 'library', 'assistant', 'stories']
ORDER = FIRST + [k for _g, _label, keys in GROUPS for k in keys if k not in FIRST]


def _sub(obj) -> str:
    """Вторая строка записи: цена, зарплата, дата поездки, город — что у объекта есть."""
    parts = []
    if hasattr(obj, 'departs_at') and obj.departs_at:
        parts.append(timezone.localtime(obj.departs_at).strftime('%d.%m %H:%M'))
    for name in ('salary', 'price_text'):
        if getattr(obj, name, ''):
            parts.append(str(getattr(obj, name)))
            break
    else:
        price = getattr(obj, 'price', None)
        if price is not None and hasattr(obj, 'currency'):
            parts.append(str(_('Даром')) if not price else f'{int(price):,} {obj.currency}'.replace(',', ' '))
    if getattr(obj, 'city', ''):
        parts.append(obj.city)
    return ' · '.join(parts[:2])


def _pub_rows(module: str) -> dict:
    """Свежие записи раздела и сколько их всего (одобренные и не скрытые). Одинаково для всех — из кеша на 2 минуты."""
    from .publications import BY_KEY
    key = f'showcase:pub:{module}'
    data = cache.get(key)
    if data is None:
        rows, total = [], 0
        for pub_key in PUBS[module]:
            pub = BY_KEY[pub_key]
            model = pub.get_model()
            qs = model.objects.all()
            if any(f.name == 'status' for f in model._meta.fields):
                qs = qs.filter(status=Moderation.APPROVED)
            if pub.active:
                qs = qs.filter(**{pub.active: True})
            if hasattr(model, 'departs_at'):
                qs = qs.filter(departs_at__gte=timezone.now()).order_by('departs_at')
            else:
                qs = qs.order_by('-pk')
            total += qs.count()
            for obj in qs[:ROWS]:
                photo = getattr(obj, 'photo', None) or getattr(obj, 'cover', None)
                rows.append({'title': pub.title_of(obj), 'sub': _sub(obj), 'url': pub.url_of(obj), 'image': photo.url if photo else ''})
        data = {'items': rows[:ROWS], 'count': total}
        cache.set(key, data, 120)
    return data


def _personal(user, module: str) -> dict | None:
    """Плитки, где показано личное: чаты, трекер, намаз, сообщества, лента, новости. None — обычная плитка с описанием."""
    if module == 'chat' and user.is_authenticated:
        from apps.chat import persona
        from apps.chat import services as chat
        rows, unread = [], 0
        for t, o, _m in chat.inbox(user, limit=40):
            if t.unread:
                unread += t.unread
                if len(rows) < ROWS:
                    name = t.title if t.is_room else (persona.name_in(t, o) if o else str(_('чат')))
                    rows.append({'title': name, 'sub': str(_('новых: {n}')).format(n=t.unread), 'url': f'/chat/{t.pk}/', 'image': ''})
        return {'items': rows, 'note': str(_('новых сообщений: {n}')).format(n=unread) if unread else str(_('новых сообщений нет')), 'hot': bool(unread)}
    if module == 'tracker' and user.is_authenticated:
        from apps.tracker import services as tracker
        day = tracker.day_view(user, timezone.localdate())
        left = [x for x in day['items'] if not x['done']][:ROWS]
        return {'items': [{'title': x['title'], 'sub': '', 'url': '/tracker/', 'image': ''} for x in left],
                'note': str(_('{done} из {total} на сегодня')).format(done=day['done'], total=day['total']) if day['total'] else str(_('добавьте первую привычку')),
                'hot': bool(day['total'] and day['done'] < day['total'])}
    if module == 'prayer':
        from apps.prayer.cities import CITIES, DEFAULT_CITY
        from apps.prayer.services import compute_for_city, until_next
        want = (getattr(user, 'city', '') or '').strip().lower()
        city = next((k for k, row in CITIES.items() if want and (want == k or str(row[0]).lower() == want)), DEFAULT_CITY)
        nxt = until_next(compute_for_city(city))
        return {'items': [], 'note': f"{nxt['name']} · {nxt['time']} · {_('через')} {nxt['human']}", 'hot': True}
    if module == 'communities' and user.is_authenticated:
        from apps.chat import spaces
        mine = spaces.mine(user)[:ROWS]
        return {'items': [{'title': s.title, 'sub': str(_('участников: {n}')).format(n=s.members_count), 'url': f'/communities/{s.pk}/',
                           'image': s.icon.url if s.icon else ''} for s in mine],
                'note': str(_('моих сообществ: {n}')).format(n=len(mine)) if mine else str(_('найдите клуб по интересам'))}
    if module == 'news':
        from apps.news.models import NewsPost
        rows = cache.get('showcase:news')
        if rows is None:
            rows = [{'title': n.title, 'sub': '', 'url': f'/news/{n.slug}/', 'image': n.cover.url if getattr(n, 'cover', None) else ''}
                    for n in NewsPost.objects.order_by('-is_pinned', '-created_at')[:ROWS]]
            cache.set('showcase:news', rows, 300)
        return {'items': rows}
    if module == 'feed':
        from apps.social import services as social
        posts = list(social.visible_posts(user if user.is_authenticated else None).exclude(text='')[:ROWS])
        return {'items': [{'title': p.text[:70], 'sub': p.author.get_display_name(), 'url': f'/feed/post/{p.pk}/', 'image': ''} for p in posts]}
    if module == 'nikah' and user.is_authenticated:
        has = getattr(user, 'nikah_profile', None) is not None
        return {'items': [], 'note': str(_('ваша анкета создана')) if has else str(_('создайте анкету — это отдельный профиль'))}
    return None


def widget(user, m) -> dict:
    """Плитка раздела m (ModuleConfig)."""
    from .templatetags.dbtr import tr
    key = m.key
    out = {'key': key, 'title': tr(m.name), 'url': f'/{key}/', 'color': COLORS.get(key, DEFAULT_COLOR), 'icon': m.icon,
           'descr': str(DESCR.get(key, '')), 'items': [], 'note': '', 'count': None, 'hot': False, 'action': None}
    extra = _personal(user, key)
    if extra is None and key in PUBS:
        extra = _pub_rows(key)
    if extra:
        out.update(extra)
    if key in ACTIONS:
        label, url = ACTIONS[key]
        out['action'] = {'label': str(label), 'url': url}
    return out


def _prefs(user) -> tuple[list, set]:
    ui = (getattr(user, 'ui', None) or {}) if getattr(user, 'is_authenticated', False) else {}
    order = [k for k in ui.get('widgets', []) if isinstance(k, str)]
    return order, {k for k in ui.get('widgets_off', []) if isinstance(k, str)}


def widgets(user) -> dict:
    """Плитки для человека: {'items': [...видимые по порядку], 'hidden': [{'key','title'}]}."""
    from .templatetags.dbtr import tr
    mods = {m.key: m for m in ModuleConfig.objects.filter(status=ModuleConfig.ON) if m.key not in SKIP}
    order, off = _prefs(user)
    base = [k for k in ORDER if k in mods] + [k for k in mods if k not in ORDER]
    keys = [k for k in order if k in mods] + [k for k in base if k not in order]
    return {'items': [widget(user, mods[k]) for k in keys if k not in off],
            'hidden': [{'key': k, 'title': tr(mods[k].name)} for k in keys if k in off]}


def arrange(user, key: str, action: str) -> None:
    """Настроить витрину под себя: 'up' / 'down' — переставить плитку, 'hide' / 'show' — убрать и вернуть."""
    mods = {m.key for m in ModuleConfig.objects.filter(status=ModuleConfig.ON) if m.key not in SKIP}
    if key not in mods or action not in ('up', 'down', 'hide', 'show'):
        return
    order, off = _prefs(user)
    base = [k for k in ORDER if k in mods] + [k for k in sorted(mods) if k not in ORDER]
    keys = [k for k in order if k in mods] + [k for k in base if k not in order]
    if action == 'hide':
        off.add(key)
    elif action == 'show':
        off.discard(key)
    else:
        shown = [k for k in keys if k not in off]
        if key in shown:
            i = shown.index(key)
            j = i - 1 if action == 'up' else i + 1
            if 0 <= j < len(shown):
                a, b = keys.index(shown[i]), keys.index(shown[j])
                keys[a], keys[b] = keys[b], keys[a]
    ui = dict(user.ui or {})
    ui['widgets'], ui['widgets_off'] = keys, sorted(off)
    user.ui = ui
    user.save(update_fields=['ui'])


def home_view(request) -> str:
    """Какой вид главной открыть: 'showcase' (витрина, по умолчанию) или 'brief' (сводка). ?view= — переключить и запомнить."""
    want = request.GET.get('view', '')
    user = request.user
    if want in ('showcase', 'brief'):
        if user.is_authenticated and (user.ui or {}).get('home_view') != want:
            user.ui = {**(user.ui or {}), 'home_view': want}
            user.save(update_fields=['ui'])
        return want
    if user.is_authenticated and (user.ui or {}).get('home_view') in ('showcase', 'brief'):
        return user.ui['home_view']
    return request.COOKIES.get('ilm4_home') if request.COOKIES.get('ilm4_home') in ('showcase', 'brief') else 'showcase'
